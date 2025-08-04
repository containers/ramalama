import http.server
import json
from datetime import datetime

from ramalama.daemon.api.model import ModelDetailsResponse, ModelResponse, model_list_to_dict
from ramalama.daemon.handler.base import APIHandler
from ramalama.model import trim_model_name
from ramalama.model_store.global_store import GlobalModelStore


class DaemonAPIHandler(APIHandler):

    PATH_PREFIX = "/api"

    def __init__(self, model_store_path):
        self.model_store_path = model_store_path

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        if handler.path.startswith(f"{DaemonAPIHandler.PATH_PREFIX}/tags"):
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
            return

        raise Exception("Unsupported GET request path")

    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler):
        pass
