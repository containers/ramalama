import os
import platform
import random
import shlex
import socket
import sys
import time
from typing import Optional

import ramalama.chat as chat
from ramalama.common import (
    MNT_DIR,
    MNT_FILE_DRAFT,
    accel_image,
    check_metal,
    check_nvidia,
    exec_cmd,
    genname,
    is_split_file_model,
    perror,
    set_accel_env_vars,
)
from ramalama.config import CONFIG, DEFAULT_PORT, DEFAULT_PORT_RANGE
from ramalama.console import should_colorize
from ramalama.engine import Engine, dry_run
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
from ramalama.rag import rag_image
from ramalama.version import version

MODEL_TYPES = ["file", "https", "http", "oci", "huggingface", "hf", "modelscope", "ms", "ollama"]


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


class NoRefFileFound(Exception):

    def __init__(self, model: str, *args):
        super().__init__(*args)

        self.model = model

    def __str__(self):
        return f"No ref file or models found for '{self.model}'. Please pull model."


def trim_model_name(model):
    if model.startswith("huggingface://"):
        model = model.replace("huggingface://", "hf://", 1)

    if not model.startswith("ollama://") and not model.startswith("oci://"):
        model = model.removesuffix(":latest")

    return model


class ModelBase:
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

    def remove(self, args):
        raise self.__not_implemented_error("rm")

    def bench(self, args):
        raise self.__not_implemented_error("bench")

    def run(self, args):
        raise self.__not_implemented_error("run")

    def perplexity(self, args):
        raise self.__not_implemented_error("perplexity")

    def serve(self, args):
        raise self.__not_implemented_error("serve")

    def exists(self) -> bool:
        raise self.__not_implemented_error("exists")

    def inspect(self, args):
        raise self.__not_implemented_error("inspect")


class Model(ModelBase):
    """Model super class"""

    model = ""
    type = "Model"

    def __init__(self, model, model_store_path):
        self.model = model

        split = self.model.rsplit("/", 1)
        self.directory = split[0] if len(split) > 1 else ""
        self.filename = split[1] if len(split) > 1 else split[0]

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

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None or not ref_file.model_files:
            raise NoRefFileFound(self.model)

        # Use the first model file
        if is_split_file_model(self.model_name):
            # Find model file with index 1 for split models
            index_models = [file for file in ref_file.model_files if "-00001-of-" in file.name]
            if len(index_models) != 1:
                raise Exception(f"Found multiple index 1 gguf models: {index_models}")
            model_file = index_models[0]
        else:
            model_file = ref_file.model_files[0]

        if use_container or should_generate:
            return os.path.join(MNT_DIR, model_file.name)
        return self.model_store.get_blob_file_path(model_file.hash)

    def _get_mmproj_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> Optional[str]:
        """
        Returns the path to the mmproj blob on the host if use_container and should_generate are both False.
        Or returns the path to the mounted file inside a container.
        """
        if dry_run:
            return ""

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

        ref_file = self.model_store.get_ref_file(self.model_tag)
        if ref_file is None:
            raise NoRefFileFound(self.model)

        if not ref_file.chat_templates:
            return None

        # Use the first chat template file
        chat_template_file = ref_file.chat_templates[0]
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

    def base(self, args, name):
        # force accel_image to use -rag version. Drop TAG if it exists
        # so that accel_image will add -rag to the image specification.
        if args.image == self.default_image and getattr(args, "rag", None):
            args.image = rag_image(args.image)
        self.engine = Engine(args)
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

    def gpu_args(self, args, runner=False):
        gpu_args = []
        if args.ngl < 0:
            args.ngl = 999

        if runner:
            gpu_args += ["--ngl"]  # double dash
        else:
            gpu_args += ["-ngl"]  # single dash

        gpu_args += [f'{args.ngl}']

        if self.draft_model:
            # Use the same arg as ngl to reduce configuration space
            gpu_args += ["-ngld", f'{args.ngl}']

        gpu_args += ["--threads", f"{args.threads}"]

        return gpu_args

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

    def bench(self, args):
        self.ensure_model_exists(args)
        exec_args = self.build_exec_args_bench(args)
        self.validate_args(args)
        self.execute_command(exec_args, args)

    def run(self, args):
        # The Run command will first launch a daemonized service
        # and run chat to communicate with it.
        self.validate_args(args)

        args.port = compute_serving_port(args, quiet=args.debug)
        if args.container:
            args.name = self.get_container_name(args)

        args.noout = not args.debug

        pid = os.fork()
        if pid == 0:
            # Child process - start the server
            self._start_server(args)
            return 0
        else:
            # Parent process - connect to server and start chat
            return self._connect_and_chat(args, pid)

    def _start_server(self, args):
        """Start the server in the child process."""
        args.host = CONFIG.host
        args.generate = ""
        args.detach = True
        self.serve(args, True)

    def _connect_and_chat(self, args, server_pid):
        """Connect to the server and start chat in the parent process."""
        args.url = f"http://127.0.0.1:{args.port}"
        if getattr(args, "runtime", None) == "mlx":
            args.url += "/v1"
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

    def _handle_container_chat(self, args, server_pid):
        """Handle chat for container-based execution."""
        _, status = os.waitpid(server_pid, 0)
        if status != 0:
            raise ValueError(f"Failed to serve model {self.model_name}, for ramalama run command")

        args.ignore = getattr(args, "dryrun", False)
        for i in range(6):
            try:
                chat.chat(args)
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
                    logger.debug(f"MLX server not ready, waiting... (attempt {i+1}/{max_retries})")
                    time.sleep(3)
                    continue

            except Exception as e:
                if i >= max_retries - 1:
                    perror(f"Error: Failed to connect to MLX server after {max_retries} attempts: {e}")
                    self._cleanup_server_process(args.pid2kill)
                    raise e
                logger.debug(f"Connection attempt failed, retrying... (attempt {i+1}/{max_retries}): {e}")
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

    def _build_mlx_exec_args(self, subcommand: str, args, extra: Optional[list[str]] = None) -> list[str]:
        """Return the command-line *exec_args* for ``mlx_lm`` *subcommand*.
        Parameters
        ----------
        subcommand:
            Should just be ``"server"``
        args:
            Parsed CLI *args* namespace.
        extra:
            Optional list of extra arguments to append verbatim.
        """
        exec_args = [
            "mlx_lm.server",
            "--model",
            shlex.quote(self._get_entry_model_path(args.container, args.generate, args.dryrun)),
        ]

        if getattr(args, "temp", None):
            exec_args += ["--temp", str(args.temp)]

        if getattr(args, "seed", None):
            exec_args += ["--seed", str(args.seed)]

        if getattr(args, "context", None):
            exec_args += ["--max-tokens", str(args.context)]

        exec_args += getattr(args, "runtime_args", [])

        if extra:
            exec_args += extra

        return exec_args

    def perplexity(self, args):
        self.validate_args(args)
        self.ensure_model_exists(args)
        exec_args = self.build_exec_args_perplexity(args)
        self.execute_command(exec_args, args)

    def build_exec_args_perplexity(self, args):
        if getattr(args, "runtime", None) == "mlx":
            raise NotImplementedError("Perplexity calculation is not supported by the MLX runtime.")

        # Default llama.cpp perplexity calculation
        exec_args = ["llama-perplexity"]
        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        exec_args += ["-m", self._get_entry_model_path(args.container, False, args.dryrun)]

        return exec_args

    def exists(self) -> bool:
        _, _, all = self.model_store.get_cached_files(self.model_tag)
        return all

    def ensure_model_exists(self, args):
        if args.dryrun or self.exists():
            return

        if args.pull == "never":
            raise ValueError(f"{args.MODEL} does not exists")

        self.pull(args)

    def build_exec_args_bench(self, args):
        if getattr(args, "runtime", None) == "mlx":
            raise NotImplementedError("Benchmarking is not supported by the MLX runtime.")

        # Default llama.cpp benchmarking
        exec_args = ["llama-bench"]
        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        exec_args += ["-m", self._get_entry_model_path(args.container, False, args.dryrun)]

        return exec_args

    def validate_args(self, args):
        # MLX validation
        if getattr(args, "runtime", None) == "mlx":
            is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
            if not is_apple_silicon:
                raise ValueError("MLX runtime is only supported on macOS with Apple Silicon.")

        # If --nocontainer=False was specified return valid
        if args.container:
            return
        if args.privileged:
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

    def vllm_serve(self, args):
        exec_args = [
            "--model",
            self._get_entry_model_path(args.container, args.generate, args.dryrun),
            "--port",
            args.port,
            "--max-sequence-length",
            f"{args.context}",
        ]
        exec_args += args.runtime_args
        return exec_args

    def llama_serve(self, args):
        exec_args = ["llama-server"]
        draft_model_path = None
        if self.draft_model:
            draft_model = self.draft_model._get_entry_model_path(args.container, args.generate, args.dryrun)
            draft_model_path = MNT_FILE_DRAFT if args.container or args.generate else draft_model

        exec_args += [
            "--port",
            args.port,
            "--model",
            self._get_entry_model_path(args.container, args.generate, args.dryrun),
            "--no-warmup",
        ]
        mmproj_path = self._get_mmproj_path(args.container, args.generate, args.dryrun)
        if mmproj_path is not None:
            exec_args += ["--mmproj", mmproj_path]
        else:
            exec_args += ["--jinja"]

            # TODO: see https://github.com/containers/ramalama/issues/1202
            # chat_template_path = self._get_chat_template_path(args.container, args.generate, args.dryrun)
            # if chat_template_path is not None:
            #     exec_args += ["--chat-template-file", chat_template_path]

        if should_colorize():
            exec_args += ["--log-colors"]

        exec_args += [
            "--alias",
            self.model,
            "--ctx-size",
            f"{args.context}",
            "--temp",
            f"{args.temp}",
            "--cache-reuse",
            "256",
        ]
        exec_args += args.runtime_args

        if draft_model_path:
            exec_args += ['--model_draft', draft_model_path]

        # Placeholder for clustering, it might be kept for override
        rpc_nodes = os.getenv("RAMALAMA_LLAMACPP_RPC_NODES")
        if rpc_nodes:
            exec_args += ["--rpc", rpc_nodes]

        if args.debug:
            exec_args += ["-v"]

        if getattr(args, "webui", "") == "off":
            exec_args.extend(["--no-webui"])

        if check_nvidia() or check_metal(args):
            exec_args.extend(["--flash-attn"])
        return exec_args

    def mlx_serve(self, args):
        extra = ["--port", str(args.port), "--host", args.host]
        return self._build_mlx_exec_args("server", args, extra)

    def build_exec_args_serve(self, args):
        if args.runtime == "vllm":
            exec_args = self.vllm_serve(args)
        elif args.runtime == "mlx":
            exec_args = self.mlx_serve(args)
        else:
            exec_args = self.llama_serve(args)

        if args.seed:
            exec_args += ["--seed", args.seed]

        return exec_args

    def handle_runtime(self, args, exec_args):
        set_accel_env_vars()

        if args.runtime == "vllm":
            vllm_max_model_len = 2048
            if args.context:
                vllm_max_model_len = args.context

            exec_args.extend(
                [
                    "--max_model_len",
                    str(vllm_max_model_len),
                    "--served-model-name",
                    self.model_name,
                ]
            )

            if getattr(args, 'runtime_args', None):
                exec_args.extend(args.runtime_args)
        elif args.runtime == "mlx":
            # MLX uses the exec_args from mlx_serve
            pass
        else:
            gpu_args = self.gpu_args(args=args)
            if gpu_args is not None:
                exec_args.extend(gpu_args)

            if args.container:
                exec_args.extend(["--host", "0.0.0.0"])
            else:
                exec_args.extend(["--host", args.host])

        return exec_args

    def generate_container_config(self, args, exec_args):

        # Get the blob paths (src) and mounted paths (dest)
        model_src_path = self._get_entry_model_path(False, False, args.dryrun)
        chat_template_src_path = self._get_chat_template_path(False, False, args.dryrun)
        model_dest_path = self._get_entry_model_path(True, True, args.dryrun)
        chat_template_dest_path = self._get_chat_template_path(True, True, args.dryrun)

        if args.generate.gen_type == "quadlet":
            self.quadlet(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )
        elif args.generate.gen_type == "kube":
            self.kube(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
                args,
                exec_args,
                args.generate.output_dir,
            )
        elif args.generate.gen_type == "quadlet/kube":
            self.quadlet_kube(
                (model_src_path, model_dest_path),
                (chat_template_src_path, chat_template_dest_path),
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
            exec_cmd(exec_args, stdout2null=args.noout)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def serve(self, args, quiet=False):
        self.validate_args(args)
        self.ensure_model_exists(args)

        args.port = compute_serving_port(args, quiet=quiet or args.generate)

        exec_args = self.build_exec_args_serve(args)
        exec_args = self.handle_runtime(args, exec_args)

        if args.generate:
            self.generate_container_config(args, exec_args)
            return

        # Add rag chatbot
        if getattr(args, "rag", None):
            exec_args = [
                "bash",
                "-c",
                f"nohup {' '.join(exec_args)} &> /tmp/llama-server.log & rag_framework run /rag/vector.db",
            ]

        self.execute_command(exec_args, args)

    def quadlet(self, model_paths, chat_template_paths, args, exec_args, output_dir):
        quadlet = Quadlet(self.model_name, model_paths, chat_template_paths, args, exec_args)
        for generated_file in quadlet.generate():
            generated_file.write(output_dir)

    def quadlet_kube(self, model_paths, chat_template_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, args, exec_args)
        kube.generate().write(output_dir)

        quadlet = Quadlet(self.model_name, model_paths, chat_template_paths, args, exec_args)
        quadlet.kube().write(output_dir)

    def kube(self, model_paths, chat_template_paths, args, exec_args, output_dir):
        kube = Kube(self.model_name, model_paths, chat_template_paths, args, exec_args)
        kube.generate().write(output_dir)

    def inspect(self, args):
        self.ensure_model_exists(args)

        model_name = self.filename
        model_registry = self.type.lower()
        model_path = self._get_entry_model_path(False, False, args.dryrun)

        if GGUFInfoParser.is_model_gguf(model_path):
            gguf_info: GGUFModelInfo = GGUFInfoParser.parse(model_name, model_registry, model_path)
            print(gguf_info.serialize(json=args.json, all=args.all))
            return
        if SafetensorInfoParser.is_model_safetensor(model_name):
            safetensor_info: SafetensorModelInfo = SafetensorInfoParser.parse(model_name, model_registry, model_path)
            print(safetensor_info.serialize(json=args.json, all=args.all))
            return

        print(ModelInfoBase(model_name, model_registry, model_path).serialize(json=args.json))

    def print_pull_message(self, model_name):
        model_name = trim_model_name(model_name)
        # Write messages to stderr
        perror(f"Downloading {model_name} ...")
        perror(f"Trying to pull {model_name} ...")


def distinfo_volume():
    dist_info = "ramalama-%s.dist-info" % version()
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), dist_info)
    if not os.path.exists(path):
        return ""

    return f"-v{path}:/usr/share/ramalama/{dist_info}:ro"


def compute_ports() -> list:
    first_port = DEFAULT_PORT_RANGE[0]
    last_port = DEFAULT_PORT_RANGE[1]
    ports = list(range(first_port + 1, last_port + 1))
    random.shuffle(ports)
    # try always the first port before the randomized others
    return [first_port] + ports


def get_available_port_if_any() -> int:
    ports = compute_ports()
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


def compute_serving_port(args, quiet=False) -> str:
    # user probably specified a custom port, don't override the choice
    if getattr(args, "port", "") not in ["", str(DEFAULT_PORT)]:
        target_port = args.port
    else:
        # otherwise compute a random serving port in the range
        target_port = get_available_port_if_any()

    if target_port == 0:
        raise IOError("no available port could be detected. Please ensure you have enough free ports.")
    if not quiet:
        openai = f"http://localhost:{target_port}"
        if args.api == "llama-stack":
            perror(f"Llama Stack RESTAPI: {openai}")
            openai = openai + "/v1/openai"
            perror(f"OpenAI RESTAPI: {openai}")
    return str(target_port)
