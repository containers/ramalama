from __future__ import annotations

import copy
import os
import random
import socket
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from functools import partial
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from typing_extensions import TypeGuard

from ramalama import chat
from ramalama.common import ContainerEntryPoint
from ramalama.compose import Compose
from ramalama.config import ActiveConfig
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
    from ramalama.transports.oci.oci import OCI

from ramalama.common import (
    MNT_DIR,
    MNT_FILE_DRAFT,
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


def is_oci(transport: "Transport") -> TypeGuard["OCI"]:
    """
    Type guard to determine whether a given transport is an OCI transport.

    This assumes the transport exposes a `model_type` attribute and that
    OCI-based transports set `model_type` to the string `"oci"`.
    """
    return getattr(transport, "model_type", None) == "oci"


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
        self._model_store: Optional["ModelStore"] = None

        self.draft_model: Optional[Transport] = None

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

        if is_oci(self):
            if use_container or should_generate:
                return self.entrypoint_path()
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
            resolve_model = getattr(self, "resolve_model", None)
            if not callable(resolve_model):
                raise NotImplementedError("Ollama transport requires resolve_model; it is missing or not callable")
            args.MODEL = resolve_model()
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
        # Detached serve: use run_cmd so the process returns and the plugin can run the healthcheck
        if getattr(args, "detach", False) and getattr(args, "subcommand", "") == "serve":
            run_cmd(self.engine.exec_args, ignore_all=args.noout)
            return True
        self.engine.exec(stdout2null=args.noout)
        return True

    def setup_mounts(self, args):
        if args.dryrun:
            return

        if self.model_type == 'oci':
            strategy = getattr(self, "strategy", None)
            mount_cmd_fn = getattr(self, "mount_cmd", None)
            if strategy is None or mount_cmd_fn is None:
                raise NotImplementedError("OCI transport requires strategy and mount_cmd")
            if self.engine.use_podman or strategy.kind == "artifact":
                mount_cmd = mount_cmd_fn()
            elif self.engine.use_docker:
                output_filename = self._get_entry_model_path(args.container, True, args.dryrun)
                volume = populate_volume_from_image(self, args, os.path.basename(output_filename))
                mount_cmd = mount_cmd_fn(volume, MNT_DIR)
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

    def serve_nonblocking(self, args, cmd: list[str]) -> Optional[subprocess.Popen]:
        if args.container:
            args.name = self.get_container_name(args)

        args.host = ActiveConfig().host
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
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return process

    def _connect_and_chat(self, args, server_process):
        """Connect to the server and start chat in the parent process."""

        args.url = f"http://127.0.0.1:{args.port}/v1"

        # Model name in the chat request must match RamalamaModelContext.alias()
        chat_args = copy.deepcopy(args)
        chat_args.model = getattr(args, 'alias', f"{self.model_organization}/{self.model_name}")

        if args.container:
            return self._handle_container_chat(chat_args, server_process)
        else:
            # Store the Popen object for monitoring
            chat_args.server_process = server_process
            chat.chat(chat_args)
            return 0

    def chat_operational_args(self, args) -> "Optional[ChatOperationalArgs]":
        return None

    def wait_for_healthy(self, args):
        wait_for_healthy(args, partial(is_healthy, model_name=self.model_alias))

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

    def quadlet(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir, model_parts=None):
        quadlet = Quadlet(
            self.model_name,
            model_paths,
            chat_template_paths,
            mmproj_paths,
            args,
            exec_args,
            self.is_artifact,
            model_parts,
        )
        for generated_file in quadlet.generate():
            generated_file.write(output_dir)

    def quadlet_kube(
        self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir, model_parts=None
    ):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.is_artifact)
        kube.generate().write(output_dir)

        quadlet = Quadlet(
            kube.name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.is_artifact, model_parts
        )
        quadlet.kube().write(output_dir)

    def kube(self, model_paths, chat_template_paths, mmproj_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, mmproj_paths, args, exec_args, self.is_artifact)
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

    @property
    def is_artifact(self) -> bool:
        return False


def compute_ports(exclude: Optional[list[str]] = None) -> list[int]:
    excluded = set() if exclude is None else set(map(int, exclude))

    port_range = ActiveConfig().default_port_range
    ports = [p for p in range(port_range[0], port_range[1] + 1) if p not in excluded]

    if not ports:
        raise ValueError("All ports in the default port range were exhausted by the exclusion list.")

    first_port = ports.pop(0)
    random.shuffle(ports)
    # try always the first port before the randomized others
    return [first_port] + ports


def get_available_port_if_any(exclude: Optional[list[str]] = None) -> int:
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


def compute_serving_port(args, quiet: bool = False, exclude: Optional[list[str]] = None) -> str:
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
        if getattr(args, "api", None) == "llama-stack":
            perror(f"Llama Stack RESTAPI: {openai}")
            openai = openai + "/v1/openai"
            perror(f"OpenAI RESTAPI: {openai}")
    return str(target_port)
