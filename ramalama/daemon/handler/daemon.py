import http.server
import json
from datetime import datetime

from ramalama.arg_types import StoreArgs
from ramalama.config import CONFIG
from ramalama.daemon.dto.model import ModelDetailsResponse, ModelResponse, model_list_to_dict
from ramalama.daemon.dto.serve import ServeRequest, ServeResponse, StopServeRequest
from ramalama.daemon.handler.base import APIHandler
from ramalama.daemon.handler.proxy import ModelProxyHandler
from ramalama.daemon.logging import logger
from ramalama.daemon.model_runner.command_factory import CommandFactory
from ramalama.daemon.model_runner.runner import ManagedModel, ModelRunner
from ramalama.model import trim_model_name
from ramalama.model_factory import ModelFactory
from ramalama.model_store.global_store import GlobalModelStore


class DaemonAPIHandler(APIHandler):

    PATH_PREFIX = "/api"

    def __init__(self, model_store_path: str, model_runner: ModelRunner):
        super().__init__()

        self.model_store_path = model_store_path
        self.model_runner = model_runner

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/tags"):
            self._handle_get_tags(handler)
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
        for model, model_files in (
            GlobalModelStore(self.model_store_path).list_models(arg_engine, arg_show_container).items()
        ):
            local_timezone = datetime.now().astimezone().tzinfo

            is_partially_downloaded = any(file.is_partial for file in model_files)
            if not arg_show_all and is_partially_downloaded:
                continue

            model = trim_model_name(model)
            size_sum = 0
            last_modified = 0.0
            for file in model_files:
                size_sum += file.size
                last_modified = max(file.modified, last_modified)

            collected_models.append(
                ModelResponse(
                    name=f"{model} (partial)" if is_partially_downloaded else model,
                    modified_at=datetime.fromtimestamp(last_modified, tz=local_timezone).isoformat(),
                    size=size_sum,
                    digest="",
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
        model = ModelFactory(
            serve_request.model_name,
            StoreArgs(store=self.model_store_path, engine=None, container=False),
            transport=CONFIG.transport,
        ).create()
        cmd = CommandFactory(model, serve_request.runtime, port, serve_request.exec_args).build()

        logger.info(f"Starting model runner for {serve_request.model_name} with command: {cmd}")
        id = ModelRunner.generate_model_id(model.model_name, model.model_tag, model.model_organization)
        model = ManagedModel(id, model, cmd, port)
        self.model_runner.add_model(model)
        self.model_runner.start_model(id)

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(
            json.dumps(ServeResponse(id, f"{ModelProxyHandler.PATH_PREFIX}/{id}").to_dict(), indent=4).encode("utf-8")
        )
        handler.wfile.flush()

    def _handle_post_stop(self, handler: http.server.SimpleHTTPRequestHandler):
        content_length = int(handler.headers["Content-Length"])
        payload = handler.rfile.read(content_length).decode("utf-8")
        stop_serve_request = StopServeRequest.from_string(payload)

        logger.debug(f"Received stop serve request: {stop_serve_request.serialize()}")

        model = ModelFactory(
            stop_serve_request.model_name,
            StoreArgs(store=self.model_store_path, engine=None, container=False),
            transport=CONFIG.transport,
        ).create()

        id = ModelRunner.generate_model_id(model.model_name, model.model_tag, model.model_organization)
        self.model_runner.stop_model(id)

        handler.send_response(200)
