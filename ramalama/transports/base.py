import os
import platform
import random
import socket
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import ramalama.chat as chat
from ramalama.common import (
    MNT_DIR,
    MNT_FILE_DRAFT,
    accel_image,
    exec_cmd,
    genname,
    is_split_file_model,
    perror,
    populate_volume_from_image,
    set_accel_env_vars,
)
from ramalama.compose import Compose
from ramalama.config import CONFIG, DEFAULT_PORT_RANGE
from ramalama.engine import Engine, dry_run, is_healthy, wait_for_healthy
from ramalama.kube import Kube
from ramalama.logger import logger
from ramalama.model_inspect.base_info import ModelInfoBase
from ramalama.model_inspect.gguf_info import GGUFModelInfo
from ramalama.model_inspect.gguf_parser import GGUFInfoParser
from ramalama.model_inspect.safetensor_info import SafetensorModelInfo
from ramalama.model_inspect.safetensor_parser import SafetensorInfoParser
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.store import ModelStore
from ramalama.quadlet import Quadlet

MODEL_TYPES = ["file", "https", "http", "oci", "huggingface", "hf", "modelscope", "ms", "ollama", "rlcr"]


file_not_found = """\
RamaLama requires the "%(cmd)s" command to be installed on the host when running with --nocontainer.
RamaLama is designed to run AI Models inside of containers, where "%(cmd)s" is already installed.
Either install a package containing the "%(cmd)s" command or run the workload inside of a container.
%(error)s"""

file_not_found_in_container = """\
RamaLama requires the "%(cmd)s" command to be installed inside of the container.
RamaLama requires the server application be installed in the container images.
Either install a package containing the "%(cmd)s" command in the container or run
with the default RamaLama
$(error)s"""


class NoGGUFModelFileFound(Exception):
    pass


class SafetensorModelNotSupported(Exception):
    pass


class NoRefFileFound(Exception):
    def __init__(self, model: str, *args):
        super().__init__(*args)

        self.model = model

    def __str__(self):
        return f"No ref file found for '{self.model}'. Please pull model."


def trim_model_name(model):
    if model.startswith("huggingface://"):
        model = model.replace("huggingface://", "hf://", 1)

    if not model.startswith("ollama://") and not model.startswith("oci://"):
        model = model.removesuffix(":latest")

    return model


class TransportBase(ABC):
    model: str
    type: str

    def __not_implemented_error(self, param):
        return NotImplementedError(f"ramalama {param} for '{type(self).__name__}' not implemented")

    def login(self, args):
        raise self.__not_implemented_error("login")

    def logout(self, args):
        raise self.__not_implemented_error("logout")

    def pull(self, args):
        raise self.__not_implemented_error("pull")

    def push(self, source_model, args):
        raise self.__not_implemented_error("push")

    @abstractmethod
    def remove(self, args):
        raise self.__not_implemented_error("rm")

    @abstractmethod
    def bench(self, args, cmd: list[str]):
        raise self.__not_implemented_error("bench")

    @abstractmethod
    def run(self, args, server_cmd: list[str]):
        raise self.__not_implemented_error("run")

    @abstractmethod
    def perplexity(self, args, cmd: list[str]):
        raise self.__not_implemented_error("perplexity")

    @abstractmethod
    def serve(self, args, cmd: list[str]):
        raise self.__not_implemented_error("serve")

    @abstractmethod
    def exists(self) -> bool:
        raise self.__not_implemented_error("exists")

    @abstractmethod
    def inspect(self, args):
        raise self.__not_implemented_error("inspect")


class Transport(TransportBase):
    """Transport super class"""

    type: str = "Transport"

    def __init__(self, model: str, model_store_path: str):
        self.model = model

        split: list[str] = self.model.rsplit("/", 1)
        self.directory: str = split[0] if len(split) > 1 else ""
        self.filename: str = split[1] if len(split) > 1 else split[0]

        self._model_name: str
        self._model_tag: str
        self._model_organization: str
        self._model_type: str
        self._model_name, self._model_tag, self._model_organization = self.extract_model_identifiers()
        self._model_type = type(self).__name__.lower()

        self._model_store_path: str = model_store_path
        self._model_store: Optional[ModelStore] = None

        self.default_image = accel_image(CONFIG)

    def extract_model_identifiers(self):
        model_name = self.model
        model_tag = "latest"
        model_organization = ""

        # extract model tag from name if exists
        if ":" in model_name:
            model_name, model_tag = model_name.split(":", 1)

        # extract model organization from name if exists and update name
        split = model_name.rsplit("/", 1)
        model_organization = split[0].removeprefix("/") if len(split) > 1 else ""
        model_name = split[1] if len(split) > 1 else split[0]

        return model_name, model_tag, model_organization

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_tag(self) -> str:
        return self._model_tag

    @property
    def model_organization(self) -> str:
        return self._model_organization

    @property
    def model_type(self) -> str:
        return self._model_type

    @property
    def model_store(self) -> ModelStore:
        if self._model_store is None:
            name, _, orga = self.extract_model_identifiers()
            self._model_store = ModelStore(GlobalModelStore(self._model_store_path), name, self.model_type, orga)
        return self._model_store

    def _get_entry_model_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> str:
        """
        Returns the path to the model blob on the host if use_container and should_generate are both False.
        Or returns the path to the mounted file inside a container.
        """
        if dry_run:
            return "/path/to/model"

        if self.model_type == 'oci':
            if use_container or should_generate:
                return os.path.join(MNT_DIR, 'model.file')
            else:
                return f"oci://{self.model}"

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None:
            raise NoRefFileFound(self.model)

        gguf_files = ref_file.model_files
        safetensor_files = ref_file.safetensor_model_files
        if safetensor_files:
            if use_container or should_generate:
                return MNT_DIR
            return self.model_store.get_snapshot_directory_from_tag(self.model_tag)
        elif not gguf_files:
            raise NoGGUFModelFileFound()

        # Use the first model file
        model_file = gguf_files[0]
        if is_split_file_model(self.model_name):
            # Find model file with index 1 for split models
            index_models = [file for file in gguf_files if "-00001-of-" in file.name]
            if len(index_models) != 1:
                raise Exception(f"Found multiple index 1 gguf models: {index_models}")
            model_file = index_models[0]

        if use_container or should_generate:
            return os.path.join(MNT_DIR, model_file.name)
        return self.model_store.get_blob_file_path(model_file.hash)

    def _get_inspect_model_path(self, dry_run: bool) -> str:
        """Return a concrete file path for inspection.
        Prefer the safetensor blob if available; otherwise use the entry path.
        """
        if dry_run:
            return "/path/to/model"
        if self.model_type == 'oci':
            return self._get_entry_model_path(False, False, dry_run)
        safetensor_blob = self.model_store.get_safetensor_blob_path(self.model_tag, self.filename)
        return safetensor_blob or self._get_entry_model_path(False, False, dry_run)

    def _get_mmproj_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> Optional[str]:
        """
        Returns the path to the mmproj blob on the host if use_container and should_generate are both False.
        Or returns the path to the mounted file inside a container.
        """
        if dry_run:
            return ""

        if self.model_type == 'oci':
            return None

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None:
            raise NoRefFileFound(self.model)

        if not ref_file.mmproj_files:
            return None

        # Use the first mmproj file
        mmproj_file = ref_file.mmproj_files[0]
        if use_container or should_generate:
            return os.path.join(MNT_DIR, mmproj_file.name)
        return self.model_store.get_blob_file_path(mmproj_file.hash)

    def _get_chat_template_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> Optional[str]:
        """
        Returns the path to the chat template blob on the host if use_container and should_generate are both False.
        Or returns the path to the mounted file inside a container.
        """
        if dry_run:
            return ""

        if self.model_type == 'oci':
            return None

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None:
            raise NoRefFileFound(self.model)

        if not ref_file.chat_templates:
            return None

        # Use the last chat template file (may have been go template converted to jinja)
        chat_template_file = ref_file.chat_templates[-1]
        if use_container or should_generate:
            return os.path.join(MNT_DIR, chat_template_file.name)
        return self.model_store.get_blob_file_path(chat_template_file.hash)

    def remove(self, args):
        _, tag, _ = self.extract_model_identifiers()
        if not self.model_store.remove_snapshot(tag) and not args.ignore:
            raise KeyError(f"Model '{self.model}' not found")

    def get_container_name(self, args):
        if getattr(args, "name", None):
            return args.name

        return genname()

    def new_engine(self, args):
        return Engine(args)

    def base(self, args, name):
        if self.type == "Ollama":
            args.UNRESOLVED_MODEL = args.MODEL
            args.MODEL = self.resolve_model()
        self.engine = self.new_engine(args)
        if args.subcommand == "run" and not getattr(args, "ARGS", None) and sys.stdin.isatty():
            self.engine.add(["-i"])

        self.engine.add(
            [
                "--label",
                "ai.ramalama",
                "--name",
                name,
                "--env=HOME=/tmp",
                "--init",
            ]
        )

    def setup_container(self, args):
        name = self.get_container_name(args)
        self.base(args, name)

    def exec_model_in_container(self, cmd_args, args):
        if not args.container:
            return False

        self.setup_container(args)
        self.setup_mounts(args)

        # Make sure Image precedes cmd_args
        self.engine.add([args.image] + cmd_args)

        if args.dryrun:
            self.engine.dryrun()
            return True
        self.engine.exec(stdout2null=args.noout)
        return True

    def setup_mounts(self, args):
        if args.dryrun:
            return
        if self.model_type == 'oci':
            if self.engine.use_podman:
                mount_cmd = f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false"
            elif self.engine.use_docker:
                output_filename = self._get_entry_model_path(args.container, True, args.dryrun)
                volume = populate_volume_from_image(self, os.path.basename(output_filename))
                mount_cmd = f"--mount=type=volume,src={volume},dst={MNT_DIR},readonly"
            else:
                raise NotImplementedError(f"No compatible oci mount method for engine: {self.engine.args.engine}")
            self.engine.add([mount_cmd])
            return None

        ref_file = self.model_store.get_ref_file(self.model_tag)

        if ref_file is None:
            raise NoRefFileFound(self.model)

        # mount all files into container with file name instead of hash
        for file in ref_file.files:
            blob_path = self.model_store.get_blob_file_path(file.hash)
            mount_path = os.path.join(MNT_DIR, file.name)
            self.engine.add([f"--mount=type=bind,src={blob_path},destination={mount_path},ro{self.engine.relabel()}"])

        if self.draft_model:
            draft_model = self.draft_model._get_entry_model_path(args.container, args.generate, args.dryrun)
            self.engine.add(
                [f"--mount=type=bind,src={draft_model},destination={MNT_FILE_DRAFT},ro{self.engine.relabel()}"]
            )

    def bench(self, args, cmd: list[str]):
        set_accel_env_vars()
        self.execute_command(cmd, args)

    def run(self, args, server_cmd: list[str]):
        # The Run command will first launch a daemonized service
        # and run chat to communicate with it.

        args.noout = not args.debug

        pid = self._fork_and_serve(args, server_cmd)
        if pid:
            return self._connect_and_chat(args, pid)

    def _fork_and_serve(self, args, cmd: list[str]):
        if args.container:
            args.name = self.get_container_name(args)
        pid = os.fork()
        if pid == 0:
            # Child process - start the server
            self._start_server(args, cmd)
        return pid

    def _start_server(self, args, cmd: list[str]):
        """Start the server in the child process."""
        args.host = CONFIG.host
        args.generate = ""
        args.detach = True
        self.serve(args, cmd)

    def _connect_and_chat(self, args, server_pid):
        """Connect to the server and start chat in the parent process."""
        args.url = f"http://127.0.0.1:{args.port}/v1"
        if getattr(args, "runtime", None) == "mlx":
            args.prefix = "🍏 > "
        args.pid2kill = ""

        if args.container:
            return self._handle_container_chat(args, server_pid)
        else:
            args.pid2kill = server_pid
            if getattr(args, "runtime", None) == "mlx":
                return self._handle_mlx_chat(args)
            chat.chat(args)
            return 0

    def chat_operational_args(self, args):
        return None

    def wait_for_healthy(self, args):
        wait_for_healthy(args, is_healthy)

    def _handle_container_chat(self, args, server_pid):
        """Handle chat for container-based execution."""
        _, status = os.waitpid(server_pid, 0)
        if status != 0:
            raise ValueError(f"Failed to serve model {self.model_name}, for ramalama run command")

        if not args.dryrun:
            try:
                self.wait_for_healthy(args)
            except subprocess.TimeoutExpired as e:
                logger.error(f"Failed to serve model {self.model_name}, for ramalama run command")
                logger.error(f"{e}: logs: {e.output}")
                raise

        args.ignore = getattr(args, "dryrun", False)
        for i in range(6):
            try:
                chat.chat(args, self.chat_operational_args(args))
                break
            except Exception as e:
                if i >= 5:
                    raise e
                time.sleep(1)
        return 0

    def _handle_mlx_chat(self, args):
        """Handle chat for MLX runtime with connection retries."""
        args.ignore = getattr(args, "dryrun", False)
        args.initial_connection = True
        max_retries = 10

        for i in range(max_retries):
            try:
                if self._is_server_ready(args.port):
                    args.initial_connection = False
                    time.sleep(1)  # Give server time to stabilize
                    chat.chat(args)
                    break
                else:
                    logger.debug(f"MLX server not ready, waiting... (attempt {i + 1}/{max_retries})")
                    time.sleep(3)
                    continue

            except Exception as e:
                if i >= max_retries - 1:
                    perror(f"Error: Failed to connect to MLX server after {max_retries} attempts: {e}")
                    self._cleanup_server_process(args.pid2kill)
                    raise e
                logger.debug(f"Connection attempt failed, retrying... (attempt {i + 1}/{max_retries}): {e}")
                time.sleep(3)

        args.initial_connection = False
        return 0

    def _is_server_ready(self, port):
        """Check if the server is ready to accept connections."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                result = s.connect_ex(('127.0.0.1', int(port)))
                return result == 0
        except (socket.error, ValueError):
            return False

    def _cleanup_server_process(self, pid):
        """Clean up the server process."""
        if not pid:
            return

        import signal

        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)  # Give it time to terminate gracefully
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def perplexity(self, args, cmd: list[str]):
        set_accel_env_vars()
        self.execute_command(cmd, args)

    def exists(self) -> bool:
        _, _, all = self.model_store.get_cached_files(self.model_tag)
        return all

    def ensure_model_exists(self, args):
        self.validate_args(args)

        if args.dryrun or self.exists():
            return

        if args.pull == "never":
            raise ValueError(f"{args.MODEL} does not exist")

        self.pull(args)

    def validate_args(self, args):
        # MLX validation
        if getattr(args, "runtime", None) == "mlx":
            is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
            if not is_apple_silicon:
                raise ValueError("MLX runtime is only supported on macOS with Apple Silicon.")

        # If --nocontainer=False was specified return valid
        if args.container:
            return
        if getattr(args, "privileged", None):
            raise KeyError(
                "--nocontainer and --privileged options conflict. The --privileged option requires a container."
            )
        # If --name was not specified return valid
        if not getattr(args, "name", None):
            return
        # If --generate was specified return valid
        if getattr(args, "generate", False):
            # Do not fail on serve if user specified --generate
            return

        raise KeyError("--nocontainer and --name options conflict. The --name option requires a container.")

    def generate_container_config(self, args, exec_args):
        # Get the blob paths (src) and mounted paths (dest)
        model_src_path = self._get_entry_model_path(False, False, args.dryrun)
        chat_template_src_path = self._get_chat_template_path(False, False, args.dryrun)
        mmproj_src_path = self._get_mmproj_path(False, False, args.dryrun)
        model_dest_path = self._get_entry_model_path(True, True, args.dryrun)
        chat_template_dest_path = self._get_chat_template_path(True, True, args.dryrun)
        mmproj_dest_path = self._get_mmproj_path(True, True, args.dryrun)

        if args.generate.gen_type == "quadlet":
            self.quadlet(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                (mmproj_src_path, mmproj_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )
        elif args.generate.gen_type == "kube":
            self.kube(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                (mmproj_src_path, mmproj_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )
        elif args.generate.gen_type == "quadlet/kube":
            self.quadlet_kube(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                (mmproj_src_path, mmproj_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )
        elif args.generate.gen_type == "compose":
            self.compose(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                (mmproj_src_path, mmproj_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )

    def execute_command(self, exec_args, args):
        try:
            if self.exec_model_in_container(exec_args, args):
                return
            if args.dryrun:
                dry_run(exec_args)
                return
            exec_cmd(exec_args, stdout2null=args.noout, stderr2null=args.noout)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def serve(self, args, cmd: list[str]):
        set_accel_env_vars()

        if args.generate:
            self.generate_container_config(args, cmd)
            return

        self.execute_command(cmd, args)

    def quadlet(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        quadlet = Quadlet(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        for generated_file in quadlet.generate():
            generated_file.write(output_dir)

    def quadlet_kube(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        kube.generate().write(output_dir)

        quadlet = Quadlet(kube.name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        quadlet.kube().write(output_dir)

    def kube(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        kube.generate().write(output_dir)

    def compose(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        compose = Compose(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        compose.generate().write(output_dir)

    def inspect_metadata(self) -> Dict[str, Any]:
        model_path = self._get_entry_model_path(False, False, False)
        if GGUFInfoParser.is_model_gguf(model_path):
            return GGUFInfoParser.parse_metadata(model_path).data
        return {}

    def inspect(
        self,
        show_all: bool = False,
        show_all_metadata: bool = False,
        get_field: str = "",
        as_json: bool = False,
        dryrun: bool = False,
    ) -> None:
        model_name = self.filename
        model_registry = self.type.lower()
        model_path = self._get_inspect_model_path(dryrun)

        if GGUFInfoParser.is_model_gguf(model_path):
            if not show_all_metadata and get_field == "":
                gguf_info: GGUFModelInfo = GGUFInfoParser.parse(model_name, model_registry, model_path)
                print(gguf_info.serialize(json=as_json, all=show_all))
                return

            metadata = GGUFInfoParser.parse_metadata(model_path)
            if show_all_metadata:
                print(metadata.serialize(json=as_json))
                return
            elif get_field != "":  # If a specific field is requested, print only that field
                field_value = metadata.get(get_field)
                if field_value is None:
                    raise KeyError(f"Field '{get_field}' not found in GGUF model metadata")
                print(field_value)
                return

        if SafetensorInfoParser.is_model_safetensor(model_name):
            safetensor_info: SafetensorModelInfo = SafetensorInfoParser.parse(model_name, model_registry, model_path)
            print(safetensor_info.serialize(json=as_json, all=show_all))
            return

        print(ModelInfoBase(model_name, model_registry, model_path).serialize(json=as_json))

    def print_pull_message(self, model_name):
        model_name = trim_model_name(model_name)
        # Write messages to stderr
        perror(f"Downloading {model_name} ...")
        perror(f"Trying to pull {model_name} ...")


def compute_ports(exclude: list[str] | None = None) -> list[int]:
    exclude = exclude and set(map(int, exclude)) or set()
    ports = list(sorted(set(range(DEFAULT_PORT_RANGE[0], DEFAULT_PORT_RANGE[1] + 1)) - exclude))
    first_port = ports.pop(0)
    random.shuffle(ports)
    # try always the first port before the randomized others
    return [first_port] + ports


def get_available_port_if_any(exclude: list[str] | None = None) -> int:
    ports = compute_ports(exclude=exclude)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        chosen_port = 0
        for target_port in ports:
            logger.debug(f"Checking if {target_port} is available")
            try:
                s.bind(('localhost', target_port))
            except OSError:
                continue
            else:
                chosen_port = target_port
                break
        return chosen_port


def compute_serving_port(args, quiet: bool = False, exclude: list[str] | None = None) -> str:
    # user probably specified a custom port, don't override the choice
    if getattr(args, "port", None):
        target_port = args.port
    else:
        # otherwise compute a random serving port in the range
        target_port = get_available_port_if_any(exclude=exclude)

    if target_port == 0:
        raise IOError("no available port could be detected. Please ensure you have enough free ports.")
    if not quiet:
        openai = f"http://localhost:{target_port}"
        if args.api == "llama-stack":
            perror(f"Llama Stack RESTAPI: {openai}")
            openai = openai + "/v1/openai"
            perror(f"OpenAI RESTAPI: {openai}")
    return str(target_port)
