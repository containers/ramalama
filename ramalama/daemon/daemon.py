#!/usr/bin/env python3

import argparse
import signal
import socketserver
import threading

from ramalama.daemon.handler.ramalama import RamalamaHandler
from ramalama.daemon.logging import configure_logger, logger
from ramalama.daemon.model_runner.runner import ModelRunner


class ShutdownHandler:
    def __init__(self, server: "RamalamaServer") -> None:
        self.server = server

    def handle_kill(self, signum, frame):
        self.server.shutdown()

    def __enter__(self):
        signal.signal(signal.SIGINT, self.handle_kill)
        signal.signal(signal.SIGTERM, self.handle_kill)

    def __exit__(self, type, value, traceback):
        pass


class RamalamaServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(self, host: str, port: int, model_store_path: str, bind_and_activate=True):
        # Do not pass a RequestHandlerClass here, we will create a custom handler in finish_request
        super().__init__((host, port), None, bind_and_activate)

        self.model_store_path: str = model_store_path
        self.model_runner: ModelRunner = ModelRunner()

        self.allow_reuse_address = True

    def finish_request(self, request, client_address):
        RamalamaHandler(self.model_store_path, self.model_runner, request, client_address, self)

    def shutdown(self):
        logger.info("Shutting down ramalama daemon...")

        for name, managed_model in self.model_runner.managed_models.items():
            try:
                logger.info(f"Stopping model runner {name}...")
                managed_model.stop()
            except Exception as e:
                logger.error(f"Error stopping model runner {name}: {e}")

        super().shutdown()


def parse_args():
    parser = argparse.ArgumentParser(description="Ramalama Daemon")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model-store-path", type=str, default="/models")

    return parser.parse_args()


def run(host: str = "0.0.0.0", port: int = 8080, model_store_path: str = "/models"):
    configure_logger("DEBUG")
    logger.info(f"Starting Ramalama daemon on {host}:{port}...")
    with RamalamaServer(host, port, model_store_path) as httpd:
        with ShutdownHandler(httpd):
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            server_thread.join()


if __name__ == '__main__':
    args = parse_args()
    run(args.host, args.port, args.model_store_path)
