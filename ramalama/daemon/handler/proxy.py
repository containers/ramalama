import http.server

from ramalama.daemon.handler.base import APIHandler


class ModelProxyHandler(APIHandler):

    PATH_PREFIX = "/model"

    def __init__(self):
        super().__init__()

    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler):
        pass

    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler):
        pass
