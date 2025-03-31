import glob
import os
import platform
import random
import socket
import sys

import ramalama
from ramalama.common import (
    MNT_CHAT_TEMPLATE_FILE,
    MNT_DIR,
    MNT_FILE,
    accel_image,
    check_nvidia,
    exec_cmd,
    genname,
    get_accel_env_vars,
    run_cmd,
    set_accel_env_vars,
)
from ramalama.config import CONFIG, DEFAULT_PORT_RANGE, int_tuple_as_str
from ramalama.console import EMOJI
from ramalama.gguf_parser import GGUFInfoParser
from ramalama.kube import Kube
from ramalama.model_inspect import GGUFModelInfo, ModelInfoBase
from ramalama.model_store import ModelStore
from ramalama.quadlet import Quadlet
from ramalama.version import version

MODEL_TYPES = ["file", "https", "http", "oci", "huggingface", "hf", "ollama"]


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


class ModelBase:

    def __not_implemented_error(self, param):
        return NotImplementedError(f"ramalama {param} for '{type(self).__name__}' not implemented")

    def login(self, args):
        raise self.__not_implemented_error("login")

    def logout(self, args):
        raise self.__not_implemented_error("logout")

    def pull(self, args):
        raise self.__not_implemented_error("pull")

    def push(self, source, args):
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
    def name(self) -> str:
        return self._model_name

    @property
    def tag(self) -> str:
        return self._model_tag

    @property
    def organization(self) -> str:
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
            self.store.remove_snapshot(tag)
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

    def get_base_conman_args(self, args, name):
        return [
            args.engine,
            "run",
            "--rm",
            "-i",
            "--label",
            "ai.ramalama",
            "--name",
            name,
            "--env=HOME=/tmp",
            "--init",
        ]

    def add_privileged_options(self, conman_args, args):
        if args.privileged:
            conman_args += ["--privileged"]
        else:
            conman_args += [
                "--security-opt=label=disable",
                "--cap-drop=all",
                "--security-opt=no-new-privileges",
            ]

        return conman_args

    def add_container_labels(self, conman_args, args):
        if hasattr(args, "MODEL"):
            conman_args += ["--label", f"ai.ramalama.model={args.MODEL}"]

        if hasattr(args, "engine"):
            conman_args += ["--label", f"ai.ramalama.engine={args.engine}"]

        if hasattr(args, "runtime"):
            conman_args += ["--label", f"ai.ramalama.runtime={args.runtime}"]

        if hasattr(args, "port"):
            conman_args += ["--label", f"ai.ramalama.port={args.port}"]

        if hasattr(args, "subcommand"):
            conman_args += ["--label", f"ai.ramalama.command={args.subcommand}"]

        return conman_args

    def add_subcommand_env(self, conman_args, args):
        if EMOJI and hasattr(args, "subcommand") and args.subcommand == "run":
            if os.path.basename(args.engine) == "podman":
                conman_args += ["--env", "LLAMA_PROMPT_PREFIX=🦭 > "]
            elif os.path.basename(args.engine) == "docker":
                conman_args += ["--env", "LLAMA_PROMPT_PREFIX=🐋 > "]

        return conman_args

    def handle_podman_specifics(self, conman_args, args):
        if os.path.basename(args.engine) == "podman" and args.podman_keep_groups:
            conman_args += ["--group-add", "keep-groups"]

        return conman_args

    def handle_oci_pull(self, conman_args, args):
        self.image = accel_image(CONFIG, args)
        if not args.dryrun and os.path.basename(args.engine) == "docker" and args.pull == "newer":
            try:
                if not args.quiet:
                    print(f"Checking for newer image {self.image}")
                run_cmd([args.engine, "pull", "-q", args.image], ignore_all=True)
            except Exception:  # Ignore errors, the run command will handle it.
                pass
        else:
            conman_args += [f"--pull={args.pull}"]

        return conman_args

    def add_env_option(self, conman_args, args):
        for env in args.env:
            conman_args += ["--env", env]

        return conman_args

    def add_tty_option(self, conman_args):
        if sys.stdout.isatty() or sys.stdin.isatty():
            conman_args += ["-t"]

        return conman_args

    def add_detach_option(self, conman_args, args):
        if hasattr(args, "detach") and args.detach is True:
            conman_args += ["-d"]

        return conman_args

    def add_port_option(self, conman_args, args):
        if hasattr(args, "port"):
            conman_args += ["-p", f"{args.port}:{args.port}"]

        return conman_args

    def add_device_options(self, conman_args, args):
        if args.device:
            for device_arg in args.device:
                conman_args += ["--device", device_arg]

        if ramalama.common.podman_machine_accel:
            conman_args += ["--device", "/dev/dri"]

        for path in ["/dev/dri", "/dev/kfd", "/dev/accel", "/dev/davinci*", "/dev/devmm_svm", "/dev/hisi_hdc"]:
            for dev in glob.glob(path):
                conman_args += ["--device", dev]

        for k, v in get_accel_env_vars().items():
            # Special case for Cuda
            if k == "CUDA_VISIBLE_DEVICES":
                if os.path.basename(args.engine) == "docker":
                    conman_args += ["--gpus", "all"]
                else:
                    # newer Podman versions support --gpus=all, but < 5.0 do not
                    conman_args += ["--device", "nvidia.com/gpu=all"]

            conman_args += ["-e", f"{k}={v}"]

        return conman_args

    def add_network_option(self, conman_args, args):
        if args.network:
            conman_args += ["--network", args.network]

        return conman_args

    def add_oci_runtime(self, conman_args, args):
        if args.oci_runtime:
            conman_args += ["--runtime", args.oci_runtime]
        elif check_nvidia() == "cuda":
            if os.path.basename(args.engine) == "docker":
                conman_args += ["--runtime", "nvidia"]
            else:
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
        if not args.engine:
            return []

        name = self.get_container_name(args)
        conman_args = self.get_base_conman_args(args, name)
        conman_args = self.add_oci_runtime(conman_args, args)
        conman_args = self.add_privileged_options(conman_args, args)
        conman_args = self.add_container_labels(conman_args, args)
        conman_args = self.add_subcommand_env(conman_args, args)
        conman_args = self.handle_podman_specifics(conman_args, args)
        conman_args = self.handle_oci_pull(conman_args, args)
        conman_args = self.add_tty_option(conman_args)
        conman_args = self.add_env_option(conman_args, args)
        conman_args = self.add_detach_option(conman_args, args)
        conman_args = self.add_port_option(conman_args, args)
        conman_args = self.add_device_options(conman_args, args)
        conman_args = self.add_network_option(conman_args, args)
        conman_args = self.add_rag(conman_args, args)

        return conman_args

    def gpu_args(self, args, runner=False):
        gpu_args = []
        machine = platform.machine()
        if (
            os.getenv("HIP_VISIBLE_DEVICES")
            or os.getenv("ASAHI_VISIBLE_DEVICES")
            or os.getenv("CUDA_VISIBLE_DEVICES")
            or os.getenv("INTEL_VISIBLE_DEVICES")
            or os.getenv("ASCEND_VISIBLE_DEVICES")
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

        # for some reason the --threads option is blowing up on Docker,
        # with option not being supported by llama-run.
        # This could be something being masked in a Docker container but not
        # in a Podman container.
        if args.threads != -1 and args.engine and os.path.basename(args.engine) != "docker":
            gpu_args += ["--threads", f"{args.threads}"]

        return gpu_args

    def exec_model_in_container(self, model_path, cmd_args, args):
        if not args.container:
            return False
        conman_args = self.setup_container(args)
        if len(conman_args) == 0:
            return False

        if model_path and os.path.exists(model_path):
            conman_args += [f"--mount=type=bind,src={model_path},destination={MNT_FILE},ro"]
        else:
            conman_args += [f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models"]

        # If a chat template is available, mount it as well
        if self.store is not None:
            ref_file = self.store.get_ref_file(self.tag)
            if ref_file.chat_template_name != "":
                chat_template_path = self.store.get_snapshot_file_path(ref_file.hash, ref_file.chat_template_name)
                conman_args += [f"--mount=type=bind,src={chat_template_path},destination={MNT_CHAT_TEMPLATE_FILE},ro"]

        # Make sure Image precedes cmd_args.
        conman_args += [accel_image(CONFIG, args)] + cmd_args

        if args.dryrun:
            dry_run(conman_args)
            return True

        exec_cmd(conman_args, debug=args.debug)
        return True

    def bench(self, args):
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_bench(args, model_path)
        self.validate_args(args)
        self.execute_model(model_path, exec_args, args)

    def run(self, args):
        self.validate_args(args)
        prompt = self.build_prompt(args)
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_run(args, model_path, prompt)
        if args.keepalive:
            exec_args = ["timeout", args.keepalive] + exec_args
        self.execute_model(model_path, exec_args, args)

    def perplexity(self, args):
        self.validate_args(args)
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_perplexity(args, model_path)
        self.execute_model(model_path, exec_args, args)

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
                fhash, _, _ = self.store.get_cached_files(tag)
                return self.store.get_snapshot_file_path(fhash, self.store.model_name)
            return ""

        return os.path.join(args.store, "models", self.type, self.directory, self.filename)

    def exists(self, args):
        model_path = self.model_path(args)
        if not os.path.exists(model_path):
            return None

        return model_path

    def get_model_path(self, args):
        model_path = self.exists(args)
        if model_path:
            return model_path

        if args.dryrun:
            return "/path/to/model"

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

    def build_exec_args_run(self, args, model_path, prompt):
        exec_model_path = model_path if not args.container else MNT_FILE

        # override prompt if not set to the local call
        if EMOJI and "LLAMA_PROMPT_PREFIX" not in os.environ:
            os.environ["LLAMA_PROMPT_PREFIX"] = "🦙 > "

        exec_args = ["llama-run", "-c", f"{args.context}", "--temp", f"{args.temp}"]
        exec_args += args.runtime_args

        if args.seed:
            exec_args += ["--seed", args.seed]

        if args.debug:
            exec_args += ["-v"]

        set_accel_env_vars()
        gpu_args = self.gpu_args(args=args, runner=True)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        if self.store is not None:
            ref_file = self.store.get_ref_file(self.tag)
            if ref_file.chat_template_name != "":
                exec_args.extend(["--chat-template-file", MNT_CHAT_TEMPLATE_FILE])

        exec_args.append(exec_model_path)
        if len(prompt) > 0:
            exec_args.append(prompt)

        return exec_args

    def execute_model(self, model_path, exec_args, args):
        try:
            if self.exec_model_in_container(model_path, exec_args, args):
                return
            if args.dryrun:
                dry_run(exec_args)
                return
            exec_cmd(exec_args, args.debug)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

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

    def build_exec_args_serve(self, args, exec_model_path, chat_template_path=""):
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
            exec_args = [
                "llama-server",
                "--port",
                args.port,
                "--model",
                exec_model_path,
                "--alias",
                self.model,
                "--ctx-size",
                f"{args.context}",
                "--temp",
                f"{args.temp}",
            ] + args.runtime_args
            if chat_template_path != "":
                exec_args.extend(["--chat-template-file", chat_template_path])

            if args.debug:
                exec_args.extend(["-v"])

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
        if args.generate == "quadlet":
            self.quadlet(model_path, chat_template_path, args, exec_args)
        elif args.generate == "kube":
            self.kube(model_path, chat_template_path, args, exec_args)
        elif args.generate == "quadlet/kube":
            self.quadlet_kube(model_path, chat_template_path, args, exec_args)
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
            exec_cmd(exec_args, debug=args.debug)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def serve(self, args, quiet=False):
        self.validate_args(args)
        args.port = compute_serving_port(args.port, args.debug, quiet)

        model_path = self.get_model_path(args)
        exec_model_path = MNT_FILE if args.container or args.generate else model_path

        chat_template_path = ""
        if self.store is not None:
            ref_file = self.store.get_ref_file(self.tag)
            if ref_file.chat_template_name != "":
                chat_template_path = (
                    MNT_CHAT_TEMPLATE_FILE
                    if args.container or args.generate
                    else self.store.get_snapshot_file_path(ref_file.hash, ref_file.chat_template_name)
                )

        exec_args = self.build_exec_args_serve(args, exec_model_path, chat_template_path)

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

    def quadlet(self, model, chat_template, args, exec_args):
        quadlet = Quadlet(model, chat_template, self.image, args, exec_args)
        quadlet.generate()

    def quadlet_kube(self, model, chat_template, args, exec_args):
        kube = Kube(model, chat_template, self.image, args, exec_args)
        kube.generate()
        quadlet = Quadlet(model, chat_template, self.image, args, exec_args)
        quadlet.kube()

    def kube(self, model, chat_template, args, exec_args):
        kube = Kube(model, chat_template, self.image, args, exec_args)
        kube.generate()

    def check_valid_model_path(self, relative_target_path, model_path):
        return os.path.exists(model_path) and os.readlink(model_path) == relative_target_path

    def inspect(self, args):
        model_name = self.filename
        model_path = self.get_model_path(args)
        model_registry = self.get_model_registry(args)

        if GGUFInfoParser.is_model_gguf(model_path):
            gguf_info: GGUFModelInfo = GGUFInfoParser.parse(model_name, model_registry, model_path, args)
            print(gguf_info.serialize(json=args.json, all=args.all))
            return

        print(ModelInfoBase(model_name, model_registry, model_path).serialize(json=args.json))


def dry_run(args):
    for arg in args:
        if not arg:
            continue
        if " " in arg:
            print('"%s"' % arg, end=" ")
        else:
            print("%s" % arg, end=" ")
    print()


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


def get_available_port_if_any(debug: bool) -> int:
    ports = compute_ports()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        chosen_port = 0
        for target_port in ports:
            if debug:
                print(f"Checking if {target_port} is available")
            try:
                s.bind(('localhost', target_port))
            except OSError:
                continue
            else:
                chosen_port = target_port
                break
        return chosen_port


def compute_serving_port(port: str, debug: bool, quiet=False) -> str:
    if not port:
        raise IOError("serving port can't be empty.")
    if port != int_tuple_as_str(DEFAULT_PORT_RANGE):
        # user specified a custom port, don't override the choice
        return port
    # otherwise compute a random serving port in the range
    target_port = get_available_port_if_any(debug)

    if target_port == 0:
        raise IOError("no available port could be detected. Please ensure you have enough free ports.")
    if not quiet:
        print(f"serving on port {target_port}")
    return str(target_port)
