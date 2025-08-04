import http.server

from ramalama.daemon.handler.daemon import DaemonAPIHandler
from ramalama.daemon.handler.proxy import ModelProxyHandler


class RamalamaHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, model_store_path, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.model_store_path = model_store_path

        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def do_GET(self):
        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_store_path).handle_get(self)
        elif self.path.startswith(ModelProxyHandler.PATH_PREFIX):
            ModelProxyHandler().handle_get(self)

    def do_HEAD(self):
        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_store_path).handle_head(self)
        elif self.path.startswith(ModelProxyHandler.PATH_PREFIX):
            ModelProxyHandler().handle_head(self)

    def do_POST(self):
        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_store_path).handle_post(self)
        elif self.path.startswith(ModelProxyHandler.PATH_PREFIX):
            ModelProxyHandler().handle_post(self)

    def do_PUT(self):
        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_store_path).handle_put(self)
        elif self.path.startswith(ModelProxyHandler.PATH_PREFIX):
            ModelProxyHandler().handle_put(self)

    def do_DELETE(self):
        if self.path.startswith(DaemonAPIHandler.PATH_PREFIX):
            DaemonAPIHandler(self.model_store_path).handle_delete(self)
        elif self.path.startswith(ModelProxyHandler.PATH_PREFIX):
            ModelProxyHandler().handle_delete(self)
