#!/usr/bin/env python3

import argparse
import signal
import socketserver
import threading

from ramalama.daemon.handler.ramalama import RamalamaHandler


class ShutdownHandler:
    def __init__(self, server: "RamalamaServer") -> None:
        self.server = server

    def handle_kill(self, signum, frame):
        print("Shutting down ramalama daemon...")
        self.server.shutdown()

    def __enter__(self):
        signal.signal(signal.SIGINT, self.handle_kill)

    def __exit__(self, type, value, traceback):
        pass


class RamalamaServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(self, host: str, port: int, model_store_path: str, bind_and_activate=True):
        # Do not pass a RequestHandlerClass here, we will set it later
        super().__init__((host, port), None, bind_and_activate)

        self.model_store_path = model_store_path
        self.allow_reuse_address = True

    def finish_request(self, request, client_address):
        RamalamaHandler(self.model_store_path, request, client_address, self)


def parse_args():
    parser = argparse.ArgumentParser(description="Ramalama Daemon")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model-store-path", type=str, default="/models")

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    with RamalamaServer(args.host, args.port, args.model_store_path) as httpd:
        with ShutdownHandler(httpd):
            print(f"Starting daemon on {args.host}:{args.port}...")
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            server_thread.join()
