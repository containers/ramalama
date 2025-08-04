import http.server
from abc import ABC, abstractmethod


class APIHandler(ABC):

    @abstractmethod
    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")
