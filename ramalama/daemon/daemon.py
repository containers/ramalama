#!/usr/bin/env python3

import argparse
import signal
import socketserver
import threading
from datetime import datetime, timedelta

from ramalama.daemon.handler.ramalama import RamalamaHandler
from ramalama.daemon.logging import LogLevel, configure_logger, logger
from ramalama.daemon.service.model_runner import ModelRunner


class ShutdownHandler:
    def __init__(self, server: "RamalamaServer") -> None:
        self.server = server

    def handle_kill(self, signum, frame):
        self.server.shutdown()

    def handle_alarm(self, signum, frame):
        # check for expiration of all models, stopping them if necessary and
        # stop shutdown server if no models are running
        self.server.check_model_expiration()
        if not self.server.model_runner.managed_models:
            self.server.shutdown()
            return

        # register alarm again for next check
        signal.alarm(self.server.idle_check_interval.seconds)

    def __enter__(self):
        signal.signal(signal.SIGINT, self.handle_kill)
        signal.signal(signal.SIGTERM, self.handle_kill)

        # set initial idle check to 300s == 5min to prevent service from stopping
        # right afer being started
        signal.signal(signal.SIGALRM, self.handle_alarm)
        signal.alarm(300)

    def __exit__(self, type, value, traceback):
        pass


class RamalamaServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(
        self, host: str, port: int, model_store_path: str, idle_check_interval: timedelta, bind_and_activate=True
    ):
        # Do not pass a RequestHandlerClass here, we will create a custom handler in finish_request
        super().__init__((host, port), None, bind_and_activate)

        self.model_store_path: str = model_store_path
        self.model_runner: ModelRunner = ModelRunner()
        self.idle_check_interval = idle_check_interval

        self.allow_reuse_address = True

    def finish_request(self, request, client_address):
        RamalamaHandler(self.model_store_path, self.model_runner, request, client_address, self)

    def check_model_expiration(self):
        curr_time = datetime.now()
        for name, m in self.model_runner.managed_models.items():
            if m.expiration_date > curr_time:
                continue

            try:
                logger.info(f"Stopping expired model '{name}'...")
                self.model_runner.stop_model(m.id)
            except Exception as e:
                logger.error(f"Failed to stop expired model '{name}': {e}")

    def shutdown(self):
        logger.info("Shutting down ramalama daemon...")

        for name, managed_model in self.model_runner.managed_models.items():
            try:
                logger.info(f"Stopping model runner {name}...")
                self.model_runner.stop_model(managed_model.id)
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
    configure_logger(LogLevel.DEBUG)
    logger.debug(f"Starting Ramalama daemon on {host}:{port}...")
    with RamalamaServer(host, port, model_store_path, timedelta(seconds=10)) as httpd:
        with ShutdownHandler(httpd):
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            server_thread.join()


if __name__ == '__main__':
    args = parse_args()
    run(args.host, args.port, args.model_store_path)
