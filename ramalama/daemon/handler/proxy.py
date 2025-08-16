import http.server
import json
import urllib.request

from ramalama.daemon.dto.proxy import RunningModelResponse, running_model_list_to_dict
from ramalama.daemon.handler.base import APIHandler
from ramalama.daemon.logging import logger
from ramalama.daemon.model_runner.runner import ModelRunner


class ModelProxyHandler(APIHandler):

    PATH_PREFIX = "/model"

    def __init__(self, model_runner: ModelRunner):
        super().__init__()

        self.model_runner = model_runner

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        if handler.path == f"{ModelProxyHandler.PATH_PREFIX}":
            models: list[RunningModelResponse] = []
            for model_id, managed_model in self.model_runner.managed_models.items():
                models.append(
                    RunningModelResponse(
                        id=managed_model.id,
                        name=managed_model.model.model_name,
                        organization=managed_model.model.model_organization,
                        tag=managed_model.model.model_tag,
                        cmd=" ".join(managed_model.run_cmd),
                    )
                )

            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(running_model_list_to_dict(models), indent=4).encode("utf-8"))
            handler.wfile.flush()

            return

        self._forward_request(handler, is_referred)

    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        self._forward_request(handler, is_referred)

    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        self._forward_request(handler, is_referred)

    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        self._forward_request(handler, is_referred)

    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        self._forward_request(handler, is_referred)

    def _forward_request(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):

        model_id = ""
        path = ""

        if is_referred:
            logger.debug("request is referred")
            path = handler.path.replace("/model", "", 1)
            if "Referer" not in handler.headers:
                msg = "Something went wrong, no referer header found"
                logger.error(msg)
                handler.send_error(500, msg)
                return
            referer = handler.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

            for part in referer.split("/"):
                if part.startswith("sha256-"):
                    model_id = part
                    break
        else:
            logger.debug("request is not referred")
            path_parts = handler.path.split("/")
            if len(path_parts) < 3:
                msg = "Model id is required in the path"
                logger.error(msg)
                handler.send_error(400, msg)
                return
            model_id = path_parts[2]
            # remove the path prefix and model id in the request path
            path = handler.path.replace(f"{ModelProxyHandler.PATH_PREFIX}/{model_id}", "", 1)

        if model_id not in self.model_runner.managed_models:
            msg = f"Model with id {model_id} not found"
            logger.error(msg)
            handler.send_error(404, msg)
            return

        managed_model = self.model_runner.managed_models[model_id]
        target_url = f"http://0.0.0.0:{managed_model.port}{path}"
        method = handler.command
        headers = handler.headers
        data = None

        if 'Content-Length' in headers:
            length = int(headers['Content-Length'])
            data = handler.rfile.read(length)

        logger.debug(f"Forwarding request -X {method} {target_url}\nHEADER: {headers} \nDATA: {data}")

        try:
            request = urllib.request.Request(target_url, data=data, headers=dict(headers), method=method)
            with urllib.request.urlopen(request) as response:
                handler.send_response(response.status)

                hop_by_hop_headers = [
                    'connection',
                    'keep-alive',
                    'proxy-authenticate',
                    'proxy-authorization',
                    'te',
                    'trailers',
                    'transfer-encoding',
                    'upgrade',
                ]
                for key, value in response.getheaders():
                    if key.lower() in hop_by_hop_headers:
                        continue
                    handler.send_header(key, value)

                handler.end_headers()
                for line in response:
                    handler.wfile.write(line)
                handler.wfile.flush()

                logger.debug(f"Received response from -X {method} {target_url}\nRESPONSE: ")
        except urllib.error.HTTPError as e:
            handler.send_response(e.code)
            handler.end_headers()
            raise e
        except urllib.error.URLError as e:
            handler.send_response(500)
            handler.end_headers()
            raise e
