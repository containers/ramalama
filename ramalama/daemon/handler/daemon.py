import http.server
import json
from datetime import datetime, timedelta

from ramalama.arg_types import StoreArgs
from ramalama.cli import parse_args_from_cmd
from ramalama.command.factory import assemble_command
from ramalama.common import generate_sha256
from ramalama.config import CONFIG
from ramalama.daemon.dto.model import ModelDetailsResponse, ModelResponse, model_list_to_dict
from ramalama.daemon.dto.serve import ServeRequest, ServeResponse, StopServeRequest
from ramalama.daemon.handler.base import APIHandler
from ramalama.daemon.handler.proxy import ModelProxyHandler
from ramalama.daemon.logging import DEFAULT_LOG_DIR, logger
from ramalama.daemon.service.model_runner import ManagedModel, ModelRunner, generate_model_id
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.transports.transport_factory import TransportFactory


class DaemonAPIHandler(APIHandler):
    PATH_PREFIX = "/api"

    def __init__(self, model_runner: ModelRunner, model_store_path: str):
        super().__init__(model_runner)

        self.model_store_path = model_store_path

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/tags"):
            self._handle_get_tags(handler)
            return
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/ps"):
            self._handle_get_running_models(handler)
            return

        raise Exception("Unsupported GET request path")

    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler):
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/serve"):
            self._handle_post_serve(handler)
            return
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/stop"):
            self._handle_post_stop(handler)
            return

        raise Exception("Unsupported POST request path")

    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def _handle_get_tags(self, handler: http.server.SimpleHTTPRequestHandler):
        # get args for querying
        arg_engine = "podman"
        arg_show_container = False
        arg_show_all = True

        collected_models = []
        for model_name, model_files in (
            GlobalModelStore(self.model_store_path).list_models(arg_engine, arg_show_container).items()
        ):
            local_timezone = datetime.now().astimezone().tzinfo

            is_partially_downloaded = any(file.is_partial for file in model_files)
            if not arg_show_all and is_partially_downloaded:
                continue

            size_sum = 0
            last_modified = 0.0
            for file in model_files:
                size_sum += file.size
                last_modified = max(file.modified, last_modified)

            model = TransportFactory(
                model_name, StoreArgs(engine=arg_engine, container=arg_show_container, store=self.model_store_path)
            ).create()
            full_model_name = f"{model.model_type}://{model.model_organization}/{model.model_name}:{model.model_tag}"
            #
            # TODO: # Get model details via inspect
            #
            collected_models.append(
                ModelResponse(
                    name=model.model_name,
                    organization=model.model_organization,
                    tag=model.model_tag,
                    source=model.model_type,
                    model=full_model_name,
                    modified_at=datetime.fromtimestamp(last_modified, tz=local_timezone).isoformat(),
                    size=size_sum,
                    is_partial=is_partially_downloaded,
                    digest=generate_sha256(full_model_name, with_sha_prefix=False),
                    details=ModelDetailsResponse(
                        format="", family="", families=[], parameter_size="", quantization_level=""
                    ),
                )
            )

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(model_list_to_dict(collected_models), indent=4).encode("utf-8"))
        handler.wfile.flush()

    def _handle_post_serve(self, handler: http.server.SimpleHTTPRequestHandler):
        content_length = int(handler.headers["Content-Length"])
        payload = handler.rfile.read(content_length).decode("utf-8")
        serve_request = ServeRequest.from_string(payload)

        logger.debug(f"Received serve request: {serve_request.serialize()}")

        port = self.model_runner.next_available_port()
        model = TransportFactory(
            serve_request.model_name,
            StoreArgs(store=self.model_store_path, engine=None, container=False),
            transport=CONFIG.transport,
        ).create()

        # Use the RamaLama CLI parser to get a namespace with all variables and their
        # default values, which is then used to assemble the final inference engine command
        ramalama_cmd = ["ramalama", "--runtime", serve_request.runtime, "serve", model.model_name, "--port", str(port)]
        for arg, val in serve_request.exec_args.items():
            ramalama_cmd.extend([arg, val])
        args = parse_args_from_cmd(ramalama_cmd)
        # always log to file at the model-specific location
        args.logfile = f"{DEFAULT_LOG_DIR}/{model.model_organization}_{model.model_name}_{model.model_tag}.log"
        inference_engine_command = assemble_command(args)

        logger.info(f"Starting model runner for {serve_request.model_name} with command: {inference_engine_command}")
        managed_model = ManagedModel(model, inference_engine_command, port, timedelta(seconds=30))
        serve_path = ModelProxyHandler.build_proxy_path(model)
        self.model_runner.add_model(managed_model)
        self.model_runner.start_model(managed_model.id, serve_path)

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(ServeResponse(managed_model.id, serve_path).to_dict(), indent=4).encode("utf-8"))
        handler.wfile.flush()

    def _handle_post_stop(self, handler: http.server.SimpleHTTPRequestHandler):
        content_length = int(handler.headers["Content-Length"])
        payload = handler.rfile.read(content_length).decode("utf-8")
        stop_serve_request = StopServeRequest.from_string(payload)

        logger.debug(f"Received stop serve request: {stop_serve_request.serialize()}")

        model = TransportFactory(
            stop_serve_request.model_name,
            StoreArgs(store=self.model_store_path, engine=None, container=False),
            transport=CONFIG.transport,
        ).create()

        mid = generate_model_id(model)
        self.model_runner.stop_model(mid)

        handler.send_response(200)
        handler.end_headers()
