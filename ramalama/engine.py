import glob
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from http.client import HTTPConnection, HTTPException
from typing import Any

# Live reference for checking global vars
import ramalama.common
from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import check_nvidia, exec_cmd, get_accel_env_vars, perror, run_cmd
from ramalama.compat import NamedTemporaryFile
from ramalama.config import get_config
from ramalama.logger import logger
from ramalama.path_utils import normalize_host_path_for_container


class BaseEngine(ABC):
    """General-purpose engine for running podman or docker commands"""

    def __init__(self, args: BaseEngineArgsType) -> None:
        base = os.path.basename(args.engine)
        self.use_docker: bool = base == "docker"
        self.use_podman: bool = base == "podman"
        self.args = args
        self.exec_args: list[str] = [self.args.engine]
        self.base_args()
        self.add_labels()
        self.add_network()
        self.add_oci_runtime()
        self.add_privileged_options()
        self.add_pull_newer()
        self.handle_podman_specifics()

    @abstractmethod
    def base_args(self): ...

    def add_label(self, label: str):
        self.add(["--label", label])

    def add_name(self, name: str):
        self.add(["--name", name])

    def add_labels(self):
        add_labels(self.args, self.add_label)

    def add_pull(self, value: str) -> None:
        self.add_args("--pull", value)

    def add_pull_newer(self):
        if not self.args.dryrun and self.use_docker and getattr(self.args, "pull", None) == "newer":
            try:
                if not self.args.quiet:
                    perror(f"Checking for newer image {self.args.image}")
                run_cmd([str(self.args.engine), "pull", "-q", self.args.image], ignore_all=True)
            except Exception:  # Ignore errors, the run command will handle it.
                pass
        elif pull_value := getattr(self.args, "pull", None):
            self.add_pull(pull_value)

    def add_network(self):
        if network := getattr(self.args, "network", None):
            self.exec_args += ["--network", network]

    def add_oci_runtime(self):
        if oci_runtime := getattr(self.args, "oci_runtime", None):
            self.exec_args += ["--runtime", oci_runtime]
            return
        if check_nvidia() == "cuda":
            if self.use_docker:
                self.exec_args += ["--runtime", "nvidia"]
            elif os.access("/usr/bin/nvidia-container-runtime", os.X_OK):
                self.exec_args += ["--runtime", "/usr/bin/nvidia-container-runtime"]

    def add_privileged_options(self):
        if not getattr(self.args, "selinux", False):
            self.add_args("--security-opt=label=disable")
        if not getattr(self.args, "nocapdrop", False):
            self.add_args("--cap-drop=all")
            self.add_args("--security-opt=no-new-privileges")

    def add_device_options(self):
        request_no_device = getattr(self.args, "device", None) == ['none']
        if request_no_device:
            return

        if device_list := getattr(self.args, "device", None):
            for device_arg in device_list:
                self.exec_args += ["--device", device_arg]

        if ramalama.common.podman_machine_accel:
            self.exec_args += ["--device", "/dev/dri"]

        for path in ["/dev/dri", "/dev/kfd", "/dev/accel", "/dev/davinci*", "/dev/devmm_svm", "/dev/hisi_hdc"]:
            for dev in glob.glob(path):
                self.exec_args += ["--device", dev]

        for k, v in get_accel_env_vars().items():
            # Special case for Cuda
            if k == "CUDA_VISIBLE_DEVICES":
                if self.use_docker:
                    self.exec_args += ["--gpus", "all"]
                else:
                    # newer Podman versions support --gpus=all, but < 5.0 do not
                    self.exec_args += ["--device", "nvidia.com/gpu=all"]
            elif k == "MUSA_VISIBLE_DEVICES":
                self.exec_args += ["--env", "MTHREADS_VISIBLE_DEVICES=all"]

            self.exec_args += ["-e", f"{k}={v}"]

    def handle_podman_specifics(self):
        if getattr(self.args, "podman_keep_groups", None):
            self.exec_args += ["--group-add", "keep-groups"]

    def add(self, newargs: Sequence[str]):
        self.exec_args.extend(newargs)

    def add_args(self, *args: str) -> None:
        self.add(args)

    def add_volume(self, src: str, dest: str, *, opts="ro"):
        self.add_args("-v", f"{normalize_host_path_for_container(src)}:{dest}:{opts}{self.relabel()}")

    def dryrun(self):
        dry_run(self.exec_args)

    def run(self):
        run_cmd(self.exec_args, stdout=None)

    def run_process(self) -> subprocess.CompletedProcess:
        """Run the command and return the CompletedProcess."""
        return run_cmd(self.exec_args, encoding="utf-8")

    def exec(self, stdout2null: bool = False, stderr2null: bool = False):
        exec_cmd(self.exec_args, stdout2null, stderr2null)

    def relabel(self):
        if getattr(self.args, "selinux", False) and self.use_podman:
            return ",z"
        return ""


class Engine(BaseEngine):
    """Engine for executing 'podman run'"""

    def __init__(self, args: BaseEngineArgsType) -> None:
        super().__init__(args)
        self.add_detach_option()
        self.add_device_options()
        self.add_env_options()
        self.add_port_option()
        self.add_tty_option()

    def base_args(self) -> None:
        # For run command, do not use --rm to auto-remove container on exit
        subcommand = getattr(self.args, "subcommand", "")
        if subcommand == "run":
            self.add_args("run")
        else:
            self.add_args("run", "--rm")

    def add_name(self, name: str) -> None:
        self.add_args("--name", name)

    def add_detach_option(self) -> None:
        if getattr(self.args, "detach", False):
            self.add_args("-d")

    def add_env_option(self, value: str) -> None:
        self.add_args("--env", value)

    def add_env_options(self) -> None:
        for env in getattr(self.args, "env", []):
            self.add_env_option(env)

    def add_port_option(self) -> None:
        port = getattr(self.args, "port", "")
        if not port:
            return

        # Convert port to string for processing
        port_str = str(port)
        host = getattr(self.args, "host", "0.0.0.0")
        host = f"{host}:" if host != "0.0.0.0" else ""
        if ":" in port_str:
            self.add_args("-p", f"{host}{port_str}")
        else:
            self.add_args("-p", f"{host}{port_str}:{port_str}")

    def add_privileged_options(self) -> None:
        if getattr(self.args, "privileged", False):
            self.add_args("--privileged")
        else:
            super().add_privileged_options()

    def use_tty(self) -> bool:
        if not sys.stdin.isatty():
            return False
        if getattr(self.args, "ARGS", None):
            return False
        return getattr(self.args, "subcommand", "") == "run"

    def add_tty_option(self) -> None:
        if self.use_tty():
            self.add_args("-t")


class BuildEngine(BaseEngine):
    """Engine for executing 'podman build'"""

    def base_args(self) -> None:
        self.add_args("build", "-q", "--no-cache")
        if self.use_podman:
            self.add_args("--layers=false")

    def add_network(self) -> None:
        self.add_args("--network=none")

    def add_privileged_options(self) -> None:
        if self.use_podman:
            super().add_privileged_options()

    def add_pull(self, value: str) -> None:
        if self.use_docker:
            if value != "never":
                # docker build only accepts a --pull option with no value, meaning
                # "always try to pull any referenced images"
                self.add_args("--pull")
        else:
            # podman build does not accept a space-separated option (--pull foo), so pass it
            # as an equals-separated option (--pull=foo)
            self.add_args(f"--pull={value}")

    def build(self, cfile: str, context: str, /, *, tag: str | None = None) -> str:
        """
        Build an image using specified Containerfile path and context dir.
        If tag is provided, the image will be tagged.
        Return the ID of the built image.
        """
        if tag:
            self.add_args("-t", tag)
        self.add_args("-f", cfile, context)
        if self.args.dryrun:
            self.dryrun()
            return ""
        return self.run_process().stdout.strip()

    def build_containerfile(self, content: str, context: str, /, *, tag: str | None = None):
        """
        Build an image using the provided Containerfile content and context dir.
        If tag is provided, the image will be tagged.
        Return the ID of the built image.
        """
        with NamedTemporaryFile(delete_on_close=False) as tfile:
            tfile.write(content.encode("utf-8"))
            tfile.close()
            return self.build(tfile.name, context, tag=tag)


def dry_run(args):
    for arg in args:
        if not arg:
            continue
        if " " in arg:
            print('"%s"' % arg, end=" ")
        else:
            print("%s" % arg, end=" ")
    print()


def images(args):
    conman = str(args.engine) if args.engine is not None else None
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "images"]
    if getattr(args, "noheading", False):
        conman_args += ["--noheading"]

    if getattr(args, "notrunc", False):
        conman_args += ["--no-trunc"]

    if args.format:
        conman_args += [f"--format={args.format}"]

    try:
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return output.split("\n")
    except subprocess.CalledProcessError as e:
        perror("ramalama list command requires a running container engine")
        raise (e)


def containers(args):
    conman = str(args.engine) if args.engine is not None else None
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "ps", "-a", "--filter", "label=ai.ramalama"]
    if getattr(args, "noheading", False):
        if conman == "docker" and not args.format:
            # implement --noheading by using --format
            conman_args += ["--format={{.ID}} {{.Image}} {{.Command}} {{.CreatedAt}} {{.Status}} {{.Ports}} {{.Names}}"]
        else:
            conman_args += ["--noheading"]

    if getattr(args, "notrunc", False):
        conman_args += ["--no-trunc"]

    if args.format:
        conman_args += [f"--format={args.format}"]

    try:
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return output.split("\n")
    except subprocess.CalledProcessError as e:
        perror("ramalama list command requires a running container engine")
        raise (e)


def info(args) -> list[Any] | str | dict[str, Any]:
    conman = str(args.engine) if args.engine is not None else None
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "info", "--format", "json"]
    try:
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return json.loads(output)
    except FileNotFoundError as e:
        return str(e)


def inspect(args, name: str, format: str | None = None, ignore_stderr: bool = False):
    if not name:
        raise ValueError("must specify a container name")
    conman = str(args.engine) if args.engine is not None else None
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "inspect"]
    if format:
        conman_args += ["--format", format]

    conman_args += [name]
    return run_cmd(conman_args, ignore_stderr=ignore_stderr).stdout.decode("utf-8").strip()


def logs(args, name: str, ignore_stderr: bool = False):
    if not name:
        raise ValueError("must specify a container name")
    conman = str(args.engine) if args.engine is not None else None
    if not conman:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "logs", name]
    return run_cmd(conman_args, ignore_stderr=ignore_stderr).stdout.decode("utf-8").strip()


def stop_container(args, name: str, remove: bool = False):
    if not name:
        raise ValueError("must specify a container name")
    conman = str(args.engine) if args.engine is not None else None
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    ignore_stderr = False
    pod = ""
    try:
        pod = inspect(args, name, format="{{ .Pod }}", ignore_stderr=True)
    except Exception as e1:
        logger.debug(e1)
        try:
            pod = inspect(args, f"{name}-pod-model-server", format="{{ .Pod }}", ignore_stderr=True)
        except Exception as e2:  # Ignore errors, the stop command will handle it.
            logger.debug(e2)
            pass

    if pod != "":
        conman_args = [conman, "pod", "rm", "-t=0", "--ignore", "--force", pod]
    else:
        conman_args = [conman, "stop", "-t=0"]
        if args.ignore:
            if conman == "podman":
                conman_args += ["--ignore", str(args.ignore)]
            else:
                ignore_stderr = True

        conman_args += [name]
    try:
        run_cmd(conman_args, ignore_stderr=ignore_stderr)
    except subprocess.CalledProcessError:
        if args.ignore and conman == "docker":
            return
        else:
            raise

    # Remove the container if requested and not a pod (pods are already removed above)
    if remove and pod == "":
        conman_args = [conman, "rm"]
        if args.ignore:
            if conman == "podman":
                conman_args += ["--ignore"]
            else:
                ignore_stderr = True
        conman_args += [name]
        try:
            run_cmd(conman_args, ignore_stderr=ignore_stderr)
        except subprocess.CalledProcessError:
            if args.ignore and conman == "docker":
                return
            else:
                raise


def add_labels(args, add_label: Callable[[str], None]):
    label_map = {
        "MODEL": "ai.ramalama.model",
        "engine": "ai.ramalama.engine",
        "runtime": "ai.ramalama.runtime",
        "port": "ai.ramalama.port",
        "subcommand": "ai.ramalama.command",
    }
    for arg, label_prefix in label_map.items():
        if value := getattr(args, arg, None):
            add_label(f"{label_prefix}={value}")


def is_healthy(args, timeout: int = 3, model_name: str | None = None):
    """Check if the response from the container indicates a healthy status."""
    conn = None
    config = get_config()
    try:
        conn = HTTPConnection("127.0.0.1", args.port, timeout=timeout)
        if getattr(args, "debug", False):
            conn.set_debuglevel(1)
        if config.runtime == 'vllm':
            conn.request("GET", "/ping")
            vllm_ping_resp = conn.getresponse()
            return vllm_ping_resp.status == 200
        conn.request("GET", "/health")
        health_resp = conn.getresponse()
        health_resp.read()
        if health_resp.status not in (200, 404):
            logger.debug(f"Container {args.name} /health status code: {health_resp.status}: {health_resp.reason}")
            return False
        conn.request("GET", "/models")
        models_resp = conn.getresponse()
        if models_resp.status != 200:
            logger.debug(f"Container {args.name} /models status code {models_resp.status}: {models_resp.reason}")
            return False
        content = models_resp.read()
        if not content:
            logger.debug(f"Container {args.name} /models returned an empty response")
            return False
        body = json.loads(content)
        if "models" not in body:
            logger.debug(f"Container {args.name} /models does not include a model list in the response")
            return False
        model_names = [m["name"] for m in body["models"]]
        if not model_name:
            # FIXME: modules have a circular dependency so inline import here
            from ramalama.transports.transport_factory import New

            model_name = New(args.MODEL, args).model_alias
        if not any(model_name in name for name in model_names):
            logger.debug(
                f'Container {args.name} /models does not include "{model_name}" in the model list: {model_names}'
            )
            return False
        logger.debug(f"Container {args.name} is healthy")
        return True
    finally:
        if conn:
            conn.close()


def wait_for_healthy(args, health_func: Callable[[Any], bool], timeout=None):
    """Waits for a container to become healthy by polling its endpoint."""
    config = get_config()
    if timeout is None:
        timeout = 180 if config.runtime == "vllm" else 20
    logger.debug(f"Waiting for container {args.name} to become healthy (timeout: {timeout}s)...")
    start_time = time.time()

    display_dots = not getattr(args, "debug", False) and sys.stdin.isatty()
    n = 0
    while time.time() - start_time < timeout:
        try:
            if display_dots:
                perror('\r' + n * '.', end='', flush=True)
            if health_func(args):
                if display_dots:
                    perror('\r' + n * ' ' + '\r', end='', flush=True)
                return
        except (ConnectionError, HTTPException, UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.debug(f"Health check of container {args.name} failed, retrying... Error: {e}")
            n += 1
        time.sleep(1)

    raise subprocess.TimeoutExpired(
        f"health check of container {args.name}", timeout, output=logs(args, args.name, ignore_stderr=not args.debug)
    )
