import copy
import json
import os
import platform
import random
import socket
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

from ramalama import chat
from ramalama.common import ContainerEntryPoint
from ramalama.compose import Compose
from ramalama.config import get_config
from ramalama.engine import Engine, dry_run, is_healthy, wait_for_healthy
from ramalama.kube import Kube
from ramalama.model_inspect.base_info import ModelInfoBase
from ramalama.model_inspect.gguf_info import GGUFModelInfo
from ramalama.model_inspect.gguf_parser import GGUFInfoParser
from ramalama.model_inspect.safetensor_info import SafetensorModelInfo
from ramalama.model_inspect.safetensor_parser import SafetensorInfoParser
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.store import ModelStore
from ramalama.quadlet import Quadlet

if TYPE_CHECKING:
    from ramalama.chat import ChatOperationalArgs

from datetime import datetime, timezone

from ramalama.benchmarks.manager import BenchmarksManager
from ramalama.benchmarks.schemas import BenchmarkRecord, BenchmarkRecordV1, get_benchmark_record
from ramalama.benchmarks.utilities import parse_json, print_bench_results
from ramalama.common import (
    MNT_DIR,
    MNT_FILE_DRAFT,
    accel_image,
    exec_cmd,
    genname,
    is_split_file_model,
    perror,
    populate_volume_from_image,
    run_cmd,
    set_accel_env_vars,
)
from ramalama.logger import logger
from ramalama.path_utils import get_container_mount_path

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
    def remove(self, args) -> bool:
        raise self.__not_implemented_error("rm")

    @abstractmethod
    def bench(self, args, cmd: list[str]):
        raise self.__not_implemented_error("bench")

    @abstractmethod
    def run(self, args, cmd: list[str]):
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
    def inspect(
        self,
        show_all: bool = False,
        show_all_metadata: bool = False,
        get_field: str = "",
        as_json: bool = False,
        dryrun: bool = False,
    ) -> Any:
        raise self.__not_implemented_error("inspect")

    def inspect_metadata(self) -> dict[str, Any]:
        """
        Inspect metadata for the model.
        Default implementation raises NotImplementedError.
        """
        raise self.__not_implemented_error("inspect_metadata")


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
        self._model_store: Optional["ModelStore"] = None

        self.default_image = accel_image(get_config())
        self.draft_model: Transport | None = None

    @cached_property
    def artifact(self) -> bool:
        return self.is_artifact()

    def extract_model_identifiers(self):
        model_name = self.model
        model_tag = "latest"
        model_organization = ""

        # extract model tag from name if exists
        if ":" in model_name:
            model_name, model_tag = model_name.rsplit(":", 1)

        # extract model organization from name if exists and update name
        split = model_name.rsplit("/", 1)
        model_organization = split[0].removeprefix("/") if len(split) > 1 else ""
        model_name = split[1] if len(split) > 1 else split[0]

        return model_name, model_tag, model_organization

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_alias(self):
        return f"{self.model_organization}/{self.model_name}"

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
    def model_store(self) -> "ModelStore":
        if self._model_store is None:
            name, _, orga = self.extract_model_identifiers()
            self._model_store = ModelStore(GlobalModelStore(self._model_store_path), name, self.model_type, orga)
        return self._model_store

    def resolve_model(self) -> str:
        """
        Resolve the model name to a canonical form.
        Only implemented by transports that need it (e.g., Ollama).
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement resolve_model()")

    def mount_cmd(self) -> str:
        """
        Generate the mount command for OCI models.
        Only implemented by transports that need it (e.g., OCI).
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement mount_cmd()")

    def _get_all_model_part_paths(
        self, use_container: bool, should_generate: bool, dry_run: bool
    ) -> list[tuple[str, str]]:
        """
        Returns a list of (src_path, dest_path) tuples for all parts of a model.
        For single-file models, returns a list with one tuple.
        For multi-part models, returns a tuple for each part.
        """
        if dry_run:
            return [("/path/to/model", f"{MNT_DIR}/model.file")]

        if self.model_type == 'oci':
            # OCI models don't use this path for multi-part handling
            entry_path_src = self._get_entry_model_path(False, False, False)
            entry_path_dest = self._get_entry_model_path(True, True, False)
            return [(entry_path_src, entry_path_dest)]

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None:
            raise NoRefFileFound(self.model)

        gguf_files = ref_file.model_files
        safetensor_files = ref_file.safetensor_model_files
        if safetensor_files:
            # Safetensor models use directory mounts, not individual files
            src_path = self.model_store.get_snapshot_directory_from_tag(self.model_tag)
            if use_container or should_generate:
                dest_path = MNT_DIR
            else:
                dest_path = src_path
            return [(src_path, dest_path)]
        elif not gguf_files:
            raise NoGGUFModelFileFound()

        model_parts = []
        for model_file in gguf_files:
            if use_container or should_generate:
                dest_path = f"{MNT_DIR}/{model_file.name}"
            else:
                dest_path = self.model_store.get_blob_file_path(model_file.hash)
            src_path = self.model_store.get_blob_file_path(model_file.hash)
            model_parts.append((src_path, dest_path))

        # Sort multi-part models by filename to ensure correct order
        if len(model_parts) > 1 and any("-00001-of-" in name for _, name in model_parts):
            model_parts.sort(key=lambda x: x[1])

        return model_parts

    def _get_entry_model_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> str:
        """
        Returns the path to the model blob on the host if use_container and should_generate are both False.
        Or returns the path to the mounted file inside a container.
        """
        if dry_run:
            return "/path/to/model"

        if self.model_type == 'oci':
            if use_container or should_generate:
                if getattr(self, "artifact", False):
                    artifact_name_method = getattr(self, "artifact_name", None)
                    if artifact_name_method:
                        try:
                            return f"{MNT_DIR}/{artifact_name_method()}"
                        except subprocess.CalledProcessError:
                            pass
                return f"{MNT_DIR}/model.file"
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
            return f"{MNT_DIR}/{model_file.name}"
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
            return f"{MNT_DIR}/{mmproj_file.name}"
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
            return f"{MNT_DIR}/{chat_template_file.name}"
        return self.model_store.get_blob_file_path(chat_template_file.hash)

    def remove(self, args) -> bool:
        _, tag, _ = self.extract_model_identifiers()
        if self.model_store.remove_snapshot(tag):
            return True
        if not args.ignore:
            raise KeyError(f"Model '{self.model}' not found")
        return False

    def get_container_name(self, args):
        if getattr(args, "name", None):
            return args.name

        return genname()

    def new_engine(self, args) -> Engine:
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

        if len(cmd_args) > 0 and isinstance(cmd_args[0], ContainerEntryPoint):
            # Ignore entrypoint
            cmd_args = cmd_args[1:]

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
                mount_cmd = self.mount_cmd()
            elif self.engine.use_docker:
                output_filename = self._get_entry_model_path(args.container, True, args.dryrun)
                volume = populate_volume_from_image(self, args, os.path.basename(output_filename))
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
            # Convert path to container-friendly format (handles Windows path conversion)
            container_blob_path = get_container_mount_path(blob_path)
            mount_path = f"{MNT_DIR}/{file.name}"
            self.engine.add(
                [f"--mount=type=bind,src={container_blob_path},destination={mount_path},ro{self.engine.relabel()}"]
            )

        if self.draft_model:
            draft_model = self.draft_model._get_entry_model_path(args.container, args.generate, args.dryrun)
            # Convert path to container-friendly format (handles Windows path conversion)
            container_draft_model = get_container_mount_path(draft_model)
            mount_opts = f"--mount=type=bind,src={container_draft_model},destination={MNT_FILE_DRAFT}"
            mount_opts += f",ro{self.engine.relabel()}"
            self.engine.add([mount_opts])

    def bench(self, args, cmd: list[str]):
        set_accel_env_vars()

        output_format = getattr(args, "format", "table")

        if args.dryrun:
            if args.container:
                self.engine.dryrun()
            else:
                dry_run(cmd)

            return
        elif args.container:
            self.setup_container(args)
            self.setup_mounts(args)
            self.engine.add([args.image] + cmd)
            result = self.engine.run_process()
        else:
            result = run_cmd(cmd, encoding="utf-8")

        try:
            bench_results = parse_json(result.stdout)
        except (json.JSONDecodeError, ValueError):
            message = f"Could not parse benchmark output. Expected JSON but got:\n{result.stdout}"
            raise ValueError(message)

        base_payload: dict = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "container_image": args.image,
                "container_runtime": args.engine,
                "inference_engine": args.runtime,
                "runtime_args": cmd,
            },
        }
        results: list[BenchmarkRecord] = list()
        for bench_result in bench_results:
            result_record: BenchmarkRecordV1 = get_benchmark_record({"result": bench_result, **base_payload}, "v1")
            results.append(result_record)

        if output_format == "json":
            print(result.stdout)
        else:
            print_bench_results(results)

        config = get_config()
        if not config.benchmarks.disable:
            bench_manager = BenchmarksManager(config.benchmarks.storage_folder)
            bench_manager.save(results)

    def run(self, args, cmd: list[str]):
        # The Run command will first launch a daemonized service
        # and run chat to communicate with it.

        if len(cmd) > 0 and isinstance(cmd[0], ContainerEntryPoint):
            # Ignore entrypoint
            cmd = cmd[1:]

        process = self.serve_nonblocking(args, cmd)
        if process:
            return self._connect_and_chat(args, process)

    def serve_nonblocking(self, args, cmd: list[str]) -> subprocess.Popen | None:
        if args.container:
            args.name = self.get_container_name(args)

        args.host = get_config().host
        args.detach = True

        set_accel_env_vars()

        if args.container:
            # For container mode, set up the container and start it with subprocess
            self.setup_container(args)
            self.setup_mounts(args)
            # Make sure Image precedes cmd_args
            self.engine.add([args.image] + cmd)

            if args.dryrun:
                self.engine.dryrun()
                return None

            # Start the container using subprocess.Popen
            process = subprocess.Popen(
                self.engine.exec_args,
            )
            return process

        # Non-container mode: run the command directly with subprocess
        if args.dryrun:
            dry_run(cmd)
            return None

        process = subprocess.Popen(
            cmd,
        )
        return process

    def _connect_and_chat(self, args, server_process):
        """Connect to the server and start chat in the parent process."""
        args.url = f"http://127.0.0.1:{args.port}/v1"
        if getattr(args, "runtime", None) == "mlx":
            args.prefix = "🍏 > "

        # Model name in the chat request must match RamalamaModelContext.alias()
        chat_args = copy.deepcopy(args)
        chat_args.model = f"{self.model_organization}/{self.model_name}"

        if args.container:
            return self._handle_container_chat(chat_args, server_process)
        else:
            # Store the Popen object for monitoring
            chat_args.server_process = server_process

            if getattr(chat_args, "runtime", None) == "mlx":
                return self._handle_mlx_chat(chat_args)
            chat.chat(chat_args)
            return 0

    def chat_operational_args(self, args) -> "ChatOperationalArgs | None":
        return None

    def wait_for_healthy(self, args):
        wait_for_healthy(args, is_healthy)

    def _handle_container_chat(self, args, server_process):
        """Handle chat for container-based execution."""

        # Wait for the server process to complete (blocking)
        exit_code = server_process.wait()
        if exit_code != 0:
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
                    self._cleanup_server_process(args.server_process)
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

    def _cleanup_server_process(self, process):
        """Clean up the server process."""
        if not process:
            return

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

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

        # Get all model parts (for multi-part models)
        model_parts = self._get_all_model_part_paths(False, True, args.dryrun)

        if args.generate.gen_type == "quadlet":
            self.quadlet(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                (mmproj_src_path, mmproj_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
                model_parts,
            )
        elif args.generate.gen_type == "kube":
            self.kube(
                (model_src_path.removeprefix("oci://"), model_dest_path),
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
                model_parts,
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

        try:
            self.execute_command(cmd, args)
        except Exception as e:
            self._cleanup_server_process(args.server_process)
            raise e

    def quadlet(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir, model_parts=None):
        quadlet = Quadlet(
            self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.artifact, model_parts
        )
        for generated_file in quadlet.generate():
            generated_file.write(output_dir)

    def quadlet_kube(
        self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir, model_parts=None
    ):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.artifact)
        kube.generate().write(output_dir)

        quadlet = Quadlet(
            kube.name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.artifact, model_parts
        )
        quadlet.kube().write(output_dir)

    def kube(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.artifact)
        kube.generate().write(output_dir)

    def compose(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        compose = Compose(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args)
        compose.generate().write(output_dir)

    def inspect_metadata(self) -> dict[str, Any]:
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
    ) -> Any:
        model_name = self.filename
        model_registry = self.type.lower()
        model_path = self._get_inspect_model_path(dryrun)
        if GGUFInfoParser.is_model_gguf(model_path):
            if not show_all_metadata and get_field == "":
                gguf_info: GGUFModelInfo = GGUFInfoParser.parse(model_name, model_registry, model_path)
                return gguf_info.serialize(json=as_json, all=show_all)

            metadata = GGUFInfoParser.parse_metadata(model_path)
            if show_all_metadata:
                return metadata.serialize(json=as_json)
            elif get_field != "":  # If a specific field is requested, print only that field
                field_value = metadata.get(get_field)
                if field_value is None:
                    raise KeyError(f"Field '{get_field}' not found in GGUF model metadata")
                return field_value

        if SafetensorInfoParser.is_model_safetensor(model_name):
            safetensor_info: SafetensorModelInfo = SafetensorInfoParser.parse(model_name, model_registry, model_path)
            return safetensor_info.serialize(json=as_json, all=show_all)

        return ModelInfoBase(model_name, model_registry, model_path).serialize(json=as_json)

    def print_pull_message(self, model_name) -> None:
        model_name = trim_model_name(model_name)
        # Write messages to stderr
        perror(f"Downloading {model_name} ...")
        perror(f"Trying to pull {model_name} ...")

    def is_artifact(self) -> bool:
        return False


def compute_ports(exclude: list[str] | None = None) -> list[int]:
    excluded = set() if exclude is None else set(map(int, exclude))

    port_range = get_config().default_port_range
    ports = [p for p in range(port_range[0], port_range[1] + 1) if p not in excluded]

    if not ports:
        raise ValueError("All ports in the default port range were exhausted by the exclusion list.")

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
    if hasattr(args, 'port_override'):
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
