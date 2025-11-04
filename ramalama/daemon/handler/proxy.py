import http.server
import urllib.parse
import urllib.request

from ramalama.daemon.handler.base import APIHandler
from ramalama.daemon.logger import logger
from ramalama.daemon.service.model_runner import ModelRunner
from ramalama.transports.transport_factory import CLASS_MODEL_TYPES


class ModelProxyHandler(APIHandler):

    PATH_PREFIX = "/models"

    def __init__(self, model_runner: ModelRunner):
        super().__init__(model_runner)

        self.model_runner = model_runner

    @staticmethod
    def build_proxy_path(model: CLASS_MODEL_TYPES) -> str:
        return f"{ModelProxyHandler.PATH_PREFIX}/{model.model_organization}/{model.model_name}"

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler, is_referred: bool = False):
        if handler.path == f"{ModelProxyHandler.PATH_PREFIX}":
            self._handle_get_running_models(handler)

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

        requested_model = None
        forward_path = ""
        for path, model in self.model_runner.served_models.items():
            if path in handler.path:
                requested_model = model
                forward_path = handler.path.replace(path, "")
                if forward_path == "":
                    forward_path = "/"
                continue

        if requested_model is None:
            msg = f"No model for path '{handler.path}' found"
            logger.error(msg)
            handler.send_error(404, msg)
            return
        requested_model.update_expiration_date()

        target_url = f"http://127.0.0.1:{requested_model.port}{forward_path}"
        method = handler.command
        headers = handler.headers
        data = None

        if 'Content-Length' in headers:
            length = int(headers['Content-Length'])
            data = handler.rfile.read(length)

        logger.debug(f"Forwarding request -X {method} {target_url}\nHEADER: {headers} \nDATA: {data!r}")

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
                if key in ["Access-Control-Allow-Origin", "Cross-Origin-Embedder-Policy", "Cross-Origin-Opener-Policy"]:
                    continue

                handler.send_header(key, value)

            handler.end_headers()
            for line in response:
                handler.wfile.write(line)
            handler.wfile.flush()

            logger.debug(f"Received response from -X {method} {target_url}\nRESPONSE: ")
