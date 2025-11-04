import json
import time
from argparse import Namespace
from typing import Optional, get_args

from ramalama import engine
from ramalama.chat import chat
from ramalama.common import genname, perror, run_cmd
from ramalama.config import CONFIG, SUPPORTED_ENGINES
from ramalama.daemon.client import DaemonAPIError, DaemonClient
from ramalama.shortnames import Shortnames


class DaemonStub:

    def __init__(
        self, shortnames: Shortnames, args: Namespace, raw_args: list[str], wait_for_healthy_timeout: int = 10
    ):
        self.shortnames = shortnames
        self.cli_args = args
        self.raw_args = raw_args
        self.wait_for_healthy_timeout = wait_for_healthy_timeout

        self.client = DaemonClient("127.0.0.1", self.cli_args.port)

    @property
    def daemon_base_url(self) -> str:
        return f"http://127.0.0.1:{self.cli_args.port}"

    def prepare_serve_request(self) -> list[str]:
        # Reconstruct the "original" ramalama command since the daemon will assemble the
        # inference engine command based on this (similar to the CLI)
        exec_args: list[str] = []
        index = self.raw_args.index(self.cli_args.subcommand)
        raw_args = self.raw_args[index + 1 :]
        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            i += 1
            # skip model name for exec args
            if arg in [self.cli_args.MODEL, self.cli_args.UNRESOLVED_MODEL]:
                continue
            # skip port and host incl. value since these are not needed for the daemon
            if arg in ["--port", "-p", "--host"]:
                i += 1
                continue
            exec_args.append(arg)

        return exec_args

    def get_host_port(self, daemon_name: str) -> Optional[str]:
        try:
            container = json.loads(engine.inspect(self.cli_args, daemon_name))
            if not container:
                return None
        except Exception as ex:
            return None

        container = container[0]
        is_daemon = engine.LABEL_CONTAINER_RAMALAMA_DAEMON in container.get("Config", {}).get("Labels", {})
        if not is_daemon:
            return None

        ports = container.get("NetworkSettings", {}).get("Ports", {})
        if not ports:
            return None

        port_entry = next(iter(ports.values()))
        if not port_entry:
            return None

        return port_entry[0].get("HostPort", None)

    def serve_model(self, daemon_name: Optional[str] = None) -> Optional[str]:

        named_daemon_already_exists = False
        if daemon_name:
            host_port = self.get_host_port(daemon_name)
            if host_port:
                self.client = DaemonClient("127.0.0.1", int(host_port))
                named_daemon_already_exists = True
        else:
            daemon_name = genname("ramalama_daemon")

        if not named_daemon_already_exists:
            self.start_daemon(daemon_name)

        exec_args = self.prepare_serve_request()

        try:
            model_input = (
                self.cli_args.MODEL
                if not hasattr(self.cli_args, "UNRESOLVED_MODEL")
                else self.cli_args.UNRESOLVED_MODEL
            )
            serve_url = self.client.start_model(model_input, self.cli_args.runtime, exec_args)
            print(f"{model_input} available at: {serve_url}")
            return serve_url
        except DaemonAPIError as e:
            perror(f"Failed to start '{model_input}': {e}")
            return None

    def wait_for_model(self, serve_path: str, timeout: int = 10):
        if timeout > 0:
            start_time = time.time()
            while time.time() - start_time < self.wait_for_healthy_timeout:
                models = self.client.list_running_models()
                for model in models:
                    if model.serve_path in serve_path:
                        return
                if self.cli_args.debug:
                    print(f"{self.cli_args.MODEL} not yet served by Daemon at {serve_path}, retrying...")
                time.sleep(1)
            raise TimeoutError(f"Timeout while waiting for {self.cli_args.MODEL} to be served")

    def wait_for_daemon(self):
        if self.wait_for_healthy_timeout > 0:
            start_time = time.time()
            while time.time() - start_time < self.wait_for_healthy_timeout:
                if self.client.is_healthy():
                    return
                if self.cli_args.debug:
                    print(f"RamaLama Daemon not yet healthy at {self.daemon_base_url}, retrying...")
                time.sleep(1)
            raise TimeoutError("Health check for RamaLama Daemon timed out")

    def start_daemon(self, daemon_name: str):
        daemon_cmd = []
        daemon_model_store_dir = self.cli_args.store
        is_daemon_in_container = self.cli_args.container and self.cli_args.engine in get_args(SUPPORTED_ENGINES)

        if is_daemon_in_container:
            # If run inside a container, map the model store to the container internal directory
            daemon_model_store_dir = "/ramalama/models"

            daemon_cmd += [
                self.cli_args.engine,
                "run",
                "--pull",
                self.cli_args.pull,
                "-d",
                "-p",
                f"{self.cli_args.port}:8080",
                "-v",
                f"{self.cli_args.store}:{daemon_model_store_dir}",
                "--label",
                engine.LABEL_CONTAINER_RAMALAMA_DAEMON,
                "--name",
                daemon_name,
                self.cli_args.image,
            ]

        daemon_cmd += [
            "ramalama",
            "--store",
            daemon_model_store_dir,
            "daemon",
            "run",
            "--port",
            "8080" if is_daemon_in_container else self.cli_args.port,
            "--host",
            CONFIG.host if is_daemon_in_container else self.cli_args.host,
        ]
        run_cmd(daemon_cmd)

        self.wait_for_daemon()

        if self.cli_args.debug:
            print(f"RamaLama Daemon started on {self.daemon_base_url}")

    def chat(self, serve_path: str):
        # Overwrite the url field to mimic behavior as in transport/base.py
        # Shallow copy to not change the url param
        self.wait_for_model(serve_path)
        self.cli_args.url = f"{serve_path}/v1"
        chat(self.cli_args)


def run_daemon(args):
    from ramalama.daemon.daemon import run

    run(host=args.host, port=int(args.port), model_store_path=args.store)
