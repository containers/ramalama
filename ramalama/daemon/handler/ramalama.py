import http.server
import traceback
import urllib.error

from ramalama.daemon.handler.daemon import DaemonAPIHandler
from ramalama.daemon.handler.proxy import ModelProxyHandler
from ramalama.daemon.logging import logger
from ramalama.daemon.service.model_runner import ModelRunner


class RamalamaHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, model_store_path: str, model_runner: ModelRunner, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server

        self.model_store_path = model_store_path
        self.model_runner = model_runner

        self.setup()
        try:
            self.handle()
        except urllib.error.HTTPError as e:
            self.send_error(e.code, e.reason)
            logger.error(f"Error handling request: {e}")
            logger.debug(f"{traceback.format_exc()}")
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")
            logger.error(f"Error handling request: {e}")
            logger.debug(f"{traceback.format_exc()}")
        finally:
            self.finish()

    def do_GET(self):
        logger.debug(f"Handling GET request for path: {self.path}")

        referer = None
        if "Referer" in self.headers:
            referer = self.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_runner, self.model_store_path).handle_get(self)
            return

        is_referred = referer is not None
        if self.path.startswith(ModelProxyHandler.PATH_PREFIX) or is_referred:
            ModelProxyHandler(self.model_runner).handle_get(self, is_referred)

    def do_HEAD(self):
        logger.debug(f"Handling HEAD request for path: {self.path}")

        referer = None
        if "Referer" in self.headers:
            referer = self.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_runner, self.model_store_path).handle_head(self)
            return

        is_referred = referer is not None
        if self.path.startswith(ModelProxyHandler.PATH_PREFIX) or is_referred:
            ModelProxyHandler(self.model_runner).handle_head(self, is_referred)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.flush()

    def do_POST(self):
        logger.debug(f"Handling POST request for path: {self.path}")

        referer = None
        if "Referer" in self.headers:
            referer = self.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_runner, self.model_store_path).handle_post(self)
            return

        is_referred = referer is not None
        if self.path.startswith(ModelProxyHandler.PATH_PREFIX) or is_referred:
            ModelProxyHandler(self.model_runner).handle_post(self, is_referred)

    def do_PUT(self):
        logger.debug(f"Handling PUT request for path: {self.path}")

        referer = None
        if "Referer" in self.headers:
            referer = self.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_runner, self.model_store_path).handle_put(self)
            return

        is_referred = referer is not None
        if self.path.startswith(ModelProxyHandler.PATH_PREFIX) or is_referred:
            ModelProxyHandler(self.model_runner).handle_put(self, is_referred)

    def do_DELETE(self):
        logger.debug(f"Handling DELETE request for path: {self.path}")

        referer = None
        if "Referer" in self.headers:
            referer = self.headers["Referer"]
            logger.debug(f"Request referer: {referer}")

        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_runner, self.model_store_path).handle_delete(self)
            return

        is_referred = referer is not None
        if self.path.startswith(ModelProxyHandler.PATH_PREFIX) or is_referred:
            ModelProxyHandler(self.model_runner).handle_delete(self, is_referred)
