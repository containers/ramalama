import os
import pathlib
import platform
import random
import re
import socket
import sys

import ramalama
from ramalama.common import (
    MNT_CHAT_TEMPLATE_FILE,
    MNT_DIR,
    MNT_FILE,
    MNT_FILE_DRAFT,
    MNT_MMPROJ_FILE,
    accel_image,
    check_metal,
    check_nvidia,
    exec_cmd,
    genname,
    get_cmd_with_wrapper,
    set_accel_env_vars,
)
from ramalama.config import CONFIG, DEFAULT_PORT, DEFAULT_PORT_RANGE
from ramalama.console import EMOJI
from ramalama.engine import Engine, dry_run
from ramalama.gguf_parser import GGUFInfoParser
from ramalama.kube import Kube
from ramalama.logger import logger
from ramalama.model_inspect import GGUFModelInfo, ModelInfoBase
from ramalama.model_store import ModelStore
from ramalama.quadlet import Quadlet
from ramalama.version import version

MODEL_TYPES = ["file", "https", "http", "oci", "huggingface", "hf", "modelscope", "ms", "ollama"]
SPLIT_MODEL_RE = r'(.*)/([^/]*)-00001-of-(\d{5})\.gguf'


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


def is_split_file_model(model_path):
    """returns true if ends with -%05d-of-%05d.gguf"""
    return bool(re.match(SPLIT_MODEL_RE, model_path))


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

    def exists(self, args):
        raise self.__not_implemented_error("exists")

    def inspect(self, args):
        raise self.__not_implemented_error("inspect")


class Model(ModelBase):
    """Model super class"""

    model = ""
    type = "Model"

    def __init__(self, model):
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

        self.store: ModelStore = None

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

    def is_symlink_to(self, file_path, target_path):
        if os.path.islink(file_path):
            symlink_target = os.readlink(file_path)
            abs_symlink_target = os.path.abspath(os.path.join(os.path.dirname(file_path), symlink_target))
            abs_target_path = os.path.abspath(target_path)
            return abs_symlink_target == abs_target_path

        return False

    def garbage_collection(self, args):
        for repo in MODEL_TYPES:
            repo_dir = f"{args.store}/repos/{repo}"
            model_dir = f"{args.store}/models/{repo}"
            for root, dirs, files in os.walk(repo_dir):
                file_has_a_symlink = False
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.startswith("sha256:") or file.endswith(".gguf"):
                        file_path = os.path.join(root, file)
                        for model_root, model_dirs, model_files in os.walk(model_dir):
                            for model_file in model_files:
                                if self.is_symlink_to(os.path.join(root, model_root, model_file), file_path):
                                    file_has_a_symlink = True

                        if not file_has_a_symlink:
                            os.remove(file_path)
                            file_path = os.path.basename(file_path)
                            print(f"Deleted: {file_path}")

    def remove(self, args):
        if self.store is not None:
            _, tag, _ = self.extract_model_identifiers()
            try:
                self.store.remove_snapshot(tag)
            except OSError as e:
                if not args.ignore:
                    raise KeyError(f"removing {self.model}: {e}")
            return

        model_path = self.model_path(args)
        try:
            os.remove(model_path)
            print(f"Untagged: {self.model}")
        except OSError as e:
            if not args.ignore:
                raise KeyError(f"removing {self.model}: {e}")
        self.garbage_collection(args)

    def get_container_name(self, args):
        if hasattr(args, "name") and args.name:
            return args.name

        return genname()

    def base(self, args, name):
        # force accel_image to use -rag version. Drop TAG if it exists
        # so that accel_image will add -rag to the image specification.
        if hasattr(args, "rag") and args.rag:
            args.image = args.image.split(":")[0]
        args.image = accel_image(CONFIG, args)
        self.engine = Engine(args)
        self.engine.add(
            [
                "-i",
                "--label",
                "ai.ramalama",
                "--name",
                name,
                "--env=HOME=/tmp",
                "--init",
            ]
        )

    def add_oci_runtime(self, conman_args, args):
        if args.oci_runtime:
            conman_args += ["--runtime", args.oci_runtime]
            return conman_args
        if check_nvidia() == "cuda":
            if os.path.basename(args.engine) == "docker":
                conman_args += ["--runtime", "nvidia"]
                return conman_args
            if os.access("/usr/bin/nvidia-container-runtime", os.X_OK):
                conman_args += ["--runtime", "/usr/bin/nvidia-container-runtime"]

        return conman_args

    def add_rag(self, exec_args, args):
        if not hasattr(args, "rag") or not args.rag:
            return exec_args

        if os.path.exists(args.rag):
            rag = os.path.realpath(args.rag)
            # Added temp read write because vector database requires write access even if nothing is written
            exec_args.append(f"--mount=type=bind,source={rag},destination=/rag/vector.db,rw=true")
        else:
            exec_args.append(f"--mount=type=image,source={args.rag},destination=/rag,rw=true")

        return exec_args

    def setup_container(self, args):
        name = self.get_container_name(args)
        self.base(args, name)

    def gpu_args(self, args, runner=False):
        gpu_args = []
        machine = platform.machine()
        if (
            os.getenv("HIP_VISIBLE_DEVICES")
            or os.getenv("ASAHI_VISIBLE_DEVICES")
            or os.getenv("CUDA_VISIBLE_DEVICES")
            or os.getenv("INTEL_VISIBLE_DEVICES")
            or os.getenv("ASCEND_VISIBLE_DEVICES")
            or os.getenv("MUSA_VISIBLE_DEVICES")
            or (
                # linux and macOS report aarch64 (linux), arm64 (macOS)
                ramalama.common.podman_machine_accel
                or (machine == "aarch64" and os.path.exists("/dev/dri"))
            )
        ):
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

    def exec_model_in_container(self, model_path, cmd_args, args):
        if not args.container:
            return False

        self.setup_container(args)
        self.setup_mounts(model_path, args)
        self.handle_rag_mode(args, cmd_args)

        # Make sure Image precedes cmd_args
        self.engine.add([accel_image(CONFIG, args)] + cmd_args)

        if args.dryrun:
            self.engine.dryrun()
            return True

        self.engine.exec()
        return True

    def setup_mounts(self, model_path, args):
        if model_path and os.path.exists(model_path):
            if hasattr(self, 'split_model'):
                self.engine.add([f"--mount=type=bind,src={model_path},destination={MNT_DIR}/{self.mnt_path},ro"])

                for k, v in self.split_model.items():
                    part_path = v.model_path(args)
                    src_file = f"{part_path}"
                    dst_file = f"{MNT_DIR}/{k}"
                    self.engine.add([f"--mount=type=bind,src={src_file},destination={dst_file},ro"])
            else:
                self.engine.add([f"--mount=type=bind,src={model_path},destination={MNT_FILE},ro"])
        else:
            self.engine.add([f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models"])

        if self.draft_model:
            draft_model = self.draft_model.get_model_path(args)
            self.engine.add([f"--mount=type=bind,src={draft_model},destination={MNT_FILE_DRAFT},ro"])

        # If a chat template is available, mount it as well
        if self.store is not None:
            _, tag, _ = self.extract_model_identifiers()
            ref_file = self.store.get_ref_file(tag)
            if ref_file is not None:
                if ref_file.chat_template_name != "":
                    chat_template_path = self.store.get_snapshot_file_path(ref_file.hash, ref_file.chat_template_name)
                    self.engine.add(
                        [f"--mount=type=bind,src={chat_template_path},destination={MNT_CHAT_TEMPLATE_FILE},ro"]
                    )

                if ref_file.mmproj_name != "":
                    mmproj_path = self.store.get_snapshot_file_path(ref_file.hash, ref_file.mmproj_name)
                    self.engine.add([f"--mount=type=bind,src={mmproj_path},destination={MNT_MMPROJ_FILE},ro"])

    def handle_rag_mode(self, args, cmd_args):
        # force accel_image to use -rag version. Drop TAG if it exists
        # so that accel_image will add -rag to the image specification.
        if hasattr(args, "rag") and args.rag:
            args.image = args.image.split(":")[0]

    def bench(self, args):
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_bench(args, model_path)
        self.validate_args(args)
        self.execute_command(model_path, exec_args, args)

    def run(self, args):
        self.validate_args(args)
        prompt = self.build_prompt(args)
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_run(args, model_path, prompt)
        if args.keepalive:
            exec_args = ["timeout", args.keepalive] + exec_args
        self.execute_command(model_path, exec_args, args)

    def perplexity(self, args):
        self.validate_args(args)
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_perplexity(args, model_path)
        self.execute_command(model_path, exec_args, args)

    def build_exec_args_perplexity(self, args, model_path):
        exec_model_path = MNT_FILE if args.container else model_path
        exec_args = ["llama-perplexity"]

        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        exec_args += ["-m", exec_model_path]

        return exec_args

    def build_prompt(self, args):
        prompt = ""
        if args.ARGS:
            prompt = " ".join(args.ARGS)

        if not sys.stdin.isatty():
            inp = sys.stdin.read()
            prompt = inp + "\n\n" + prompt

        return prompt

    def model_path(self, args):
        if self.store is not None:
            _, tag, _ = self.extract_model_identifiers()
            if self.store.tag_exists(tag):
                ref_file = self.store.get_ref_file(tag)
                return str(
                    pathlib.Path(self.store.get_snapshot_file_path(ref_file.hash, ref_file.model_name)).resolve()
                )
            return ""

        return os.path.join(args.store, "models", self.type, self.directory, self.filename)

    def exists(self, args):
        model_path = self.model_path(args)
        if not os.path.exists(model_path):
            return None

        return model_path

    def get_model_path(self, args):
        if os.path.exists(args.MODEL):
            return args.MODEL

        model_path = self.exists(args)
        if model_path:
            return model_path

        if args.dryrun:
            return "/path/to/model"

        if args.pull == "never":
            raise ValueError(f"{args.MODEL} does not exists")

        model_path = self.pull(args)

        return model_path

    def get_model_registry(self, args):
        model_path = self.get_model_path(args)
        if not model_path or args.dryrun:
            return ""

        parts = model_path.replace(args.store, "").split(os.sep)
        if len(parts) < 3:
            return ""
        return parts[2]

    def build_exec_args_bench(self, args, model_path):
        exec_model_path = MNT_FILE if args.container else model_path
        exec_args = ["llama-bench"]

        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        exec_args += ["-m", exec_model_path]

        return exec_args

    def get_ramalama_core_path(self, args, exec_cmd):
        if not args.container:
            return get_cmd_with_wrapper(exec_cmd)

        return f"/usr/libexec/ramalama/{exec_cmd}"

    def build_exec_args_run(self, args, model_path, prompt):
        exec_model_path = model_path if not args.container else MNT_FILE

        # override prompt if not set to the local call
        if EMOJI and "LLAMA_PROMPT_PREFIX" not in os.environ:
            os.environ["LLAMA_PROMPT_PREFIX"] = "🦙 > "

        exec_args = [
            self.get_ramalama_core_path(args, "ramalama-run-core"),
            "--jinja",
            "-c",
            f"{args.context}",
            "--temp",
            f"{args.temp}",
        ] + args.runtime_args

        if args.seed:
            exec_args += ["--seed", args.seed]

        if args.debug:
            exec_args += ["-v"]  # Change to --debug sometime

        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args, runner=True)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        # TODO: see https://github.com/containers/ramalama/issues/1202
        # if self.store is not None:
        #     _, tag, _ = self.extract_model_identifiers()
        #     ref_file = self.store.get_ref_file(tag)
        #     if ref_file.chat_template_name != "":
        #         exec_args.extend(["--chat-template-file", MNT_CHAT_TEMPLATE_FILE])

        exec_args.append(exec_model_path)
        if len(prompt) > 0:
            exec_args.append(prompt)

        return exec_args

    def validate_args(self, args):
        if args.container:
            return
        if args.privileged:
            raise KeyError(
                "--nocontainer and --privileged options conflict. The --privileged option requires a container."
            )
        if hasattr(args, "name") and args.name:
            if hasattr(args, "generate"):
                # Do not fail on serve if user specified --generate
                if args.generate:
                    return
            raise KeyError("--nocontainer and --name options conflict. The --name option requires a container.")

    def build_exec_args_serve(self, args, exec_model_path, chat_template_path="", mmproj_path=""):
        if args.runtime == "vllm":
            exec_args = [
                "--model",
                exec_model_path,
                "--port",
                args.port,
                "--max-sequence-length",
                f"{args.context}",
            ] + args.runtime_args
        else:
            exec_args = [self.get_ramalama_core_path(args, "ramalama-serve-core")]
            draft_model_path = None
            if self.draft_model:
                draft_model = self.draft_model.get_model_path(args)
                draft_model_path = MNT_FILE_DRAFT if args.container or args.generate else draft_model

            exec_args += ["llama-server", "--port", args.port, "--model", exec_model_path]
            if mmproj_path:
                exec_args += ["--mmproj", mmproj_path]
            else:
                exec_args += ["--jinja"]

            exec_args += [
                "--alias",
                self.model,
                "--ctx-size",
                f"{args.context}",
                "--temp",
                f"{args.temp}",
                "--cache-reuse",
                "256",
            ] + args.runtime_args

            if draft_model_path:
                exec_args += ['--model_draft', draft_model_path]

            # Placeholder for clustering, it might be kept for override
            rpc_nodes = os.getenv("RAMALAMA_LLAMACPP_RPC_NODES")
            if rpc_nodes:
                exec_args += ["--rpc", rpc_nodes]

            # TODO: see https://github.com/containers/ramalama/issues/1202
            # if chat_template_path != "":
            #     exec_args += ["--chat-template-file", chat_template_path]

            if args.debug:
                exec_args += ["-v"]

            if hasattr(args, "webui") and args.webui == "off":
                exec_args.extend(["--no-webui"])

            if check_nvidia() or check_metal(args):
                exec_args.extend(["--flash-attn"])

        if args.seed:
            exec_args += ["--seed", args.seed]

        return exec_args

    def handle_runtime(self, args, exec_args, exec_model_path):
        set_accel_env_vars()
        if args.runtime == "vllm":
            exec_model_path = os.path.dirname(exec_model_path)
            # Left out "vllm", "serve" the image entrypoint already starts it
            exec_args = ["--port", args.port, "--model", MNT_FILE, "--max_model_len", "2048"]
        else:
            gpu_args = self.gpu_args(args=args)
            if gpu_args is not None:
                exec_args.extend(gpu_args)

            exec_args.extend(["--host", args.host])

        return exec_args

    def generate_container_config(self, model_path, chat_template_path, args, exec_args):
        self.image = accel_image(CONFIG, args)

        if not args.generate:
            return False

        if args.generate.gen_type == "quadlet":
            self.quadlet(model_path, chat_template_path, args, exec_args, args.generate.output_dir)
        elif args.generate.gen_type == "kube":
            self.kube(model_path, chat_template_path, args, exec_args, args.generate.output_dir)
        elif args.generate.gen_type == "quadlet/kube":
            self.quadlet_kube(model_path, chat_template_path, args, exec_args, args.generate.output_dir)
        else:
            return False

        return True

    def execute_command(self, model_path, exec_args, args):
        try:
            if self.exec_model_in_container(model_path, exec_args, args):
                return
            if args.dryrun:
                dry_run(exec_args)
                return
            exec_cmd(exec_args)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def serve(self, args, quiet=False):
        self.validate_args(args)
        model_path = self.get_model_path(args)
        if is_split_file_model(model_path):
            mnt_file = MNT_DIR + '/' + self.mnt_path
        else:
            mnt_file = MNT_FILE

        args.port = compute_serving_port(args, quiet=quiet or args.generate)
        exec_model_path = mnt_file if args.container or args.generate else model_path
        chat_template_path = ""
        mmproj_path = ""
        if self.store is not None:
            _, tag, _ = self.extract_model_identifiers()
            ref_file = self.store.get_ref_file(tag)
            if ref_file is not None:
                if ref_file.chat_template_name != "":
                    chat_template_path = (
                        MNT_CHAT_TEMPLATE_FILE
                        if args.container or args.generate
                        else self.store.get_snapshot_file_path(ref_file.hash, ref_file.chat_template_name)
                    )

                if ref_file.mmproj_name != "":
                    mmproj_path = (
                        MNT_MMPROJ_FILE
                        if args.container or args.generate
                        else self.store.get_snapshot_file_path(ref_file.hash, ref_file.mmproj_name)
                    )

        exec_args = self.build_exec_args_serve(args, exec_model_path, chat_template_path, mmproj_path)
        exec_args = self.handle_runtime(args, exec_args, exec_model_path)
        if self.generate_container_config(model_path, chat_template_path, args, exec_args):
            return

        # Add rag chatbot
        if hasattr(args, "rag") and args.rag:
            exec_args = [
                "bash",
                "-c",
                f"nohup {' '.join(exec_args)} &> /tmp/llama-server.log & rag_framework run /rag/vector.db",
            ]

        self.execute_command(model_path, exec_args, args)

    def quadlet(self, model, chat_template, args, exec_args, output_dir):
        quadlet = Quadlet(model, chat_template, self.image, args, exec_args)
        for generated_file in quadlet.generate():
            generated_file.write(output_dir)

    def quadlet_kube(self, model, chat_template, args, exec_args, output_dir):
        kube = Kube(model, chat_template, self.image, args, exec_args)
        kube.generate().write(output_dir)

        quadlet = Quadlet(model, chat_template, self.image, args, exec_args)
        quadlet.kube().write(output_dir)

    def kube(self, model, chat_template, args, exec_args, output_dir):
        kube = Kube(model, chat_template, self.image, args, exec_args)
        kube.generate().write(output_dir)

    def check_valid_model_path(self, relative_target_path, model_path):
        return os.path.exists(model_path) and os.readlink(model_path) == relative_target_path

    def inspect(self, args):
        model_name = self.filename
        model_path = self.get_model_path(args)
        model_registry = self.get_model_registry(args)

        if GGUFInfoParser.is_model_gguf(model_path):
            gguf_info: GGUFModelInfo = GGUFInfoParser.parse(model_name, model_registry, model_path)
            print(gguf_info.serialize(json=args.json, all=args.all))
            return

        print(ModelInfoBase(model_name, model_registry, model_path).serialize(json=args.json))

    def print_pull_message(self, model_name):
        print(f"Downloading {model_name} ...")
        print(f"Trying to pull {model_name} ...")


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
    if args.port not in ["", str(DEFAULT_PORT)]:
        target_port = args.port
    else:
        # otherwise compute a random serving port in the range
        target_port = get_available_port_if_any()

    if target_port == 0:
        raise IOError("no available port could be detected. Please ensure you have enough free ports.")
    if not quiet:
        openai = f"http://localhost:{target_port}"
        if args.api == "llama-stack":
            print(f"Llama Stack RESTAPI: {openai}")
            openai = openai + "/v1/openai"
        print(f"OpenAI RESTAPI: {openai}")
    return str(target_port)
