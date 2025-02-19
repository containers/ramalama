import os
import platform
import sys

from ramalama.common import (
    DEFAULT_IMAGE,
    MNT_DIR,
    MNT_FILE,
    container_manager,
    exec_cmd,
    genname,
    get_env_vars,
    get_gpu,
    run_cmd,
)
from ramalama.gguf_parser import GGUFInfoParser
from ramalama.kube import Kube
from ramalama.model_inspect import GGUFModelInfo, ModelInfoBase
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
        model_path = self.model_path(args)
        try:
            os.remove(model_path)
            print(f"Untagged: {self.model}")
        except OSError as e:
            if not args.ignore:
                raise KeyError(f"removing {self.model}: {e}")
        self.garbage_collection(args)

    def attempt_to_use_versioned(self, conman, image, vers, args):
        try:
            if run_cmd([conman, "inspect", f"{image}:{vers}"], ignore_all=True, debug=args.debug):
                return True

            return run_cmd([conman, "pull", f"{image}:{vers}"], debug=args.debug)

        except Exception:
            return False

    def _image(self, args):
        if args.image != DEFAULT_IMAGE:
            return args.image

        env_vars = get_env_vars()

        if not env_vars:
            gpu_type = None
        else:
            gpu_type, _ = next(iter(env_vars.items()))

        if args.runtime == "vllm":
            if gpu_type == "HIP_VISIBLE_DEVICES":
                return "quay.io/modh/vllm:rhoai-2.18-rocm"

            return "quay.io/modh/vllm:rhoai-2.18-cuda"

        split = version().split(".")
        vers = ".".join(split[:2])
        conman = container_manager()
        images = {
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
        }

        image = images.get(gpu_type, args.image)
        if self.attempt_to_use_versioned(conman, image, vers, args):
            return f"{image}:{vers}"

        return f"{image}:latest"

    def setup_container(self, args):
        if hasattr(args, "name") and args.name:
            name = args.name
        else:
            name = genname()

        if not args.engine:
            return []

        conman_args = [
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
        if args.privileged:
            conman_args += ["--privileged"]
        else:
            conman_args += [
                "--security-opt=label=disable",
                "--cap-drop=all",
                "--security-opt=no-new-privileges",
            ]

        container_labels = []
        if hasattr(args, "MODEL"):
            container_labels += ["--label", f"ai.ramalama.model={args.MODEL}"]
        if hasattr(args, "engine"):
            container_labels += ["--label", f"ai.ramalama.engine={args.engine}"]
        if hasattr(args, "runtime"):
            container_labels += ["--label", f"ai.ramalama.runtime={args.runtime}"]
        if hasattr(args, "port"):
            container_labels += ["--label", f"ai.ramalama.port={args.port}"]
        if hasattr(args, "subcommand"):
            container_labels += ["--label", f"ai.ramalama.command={args.subcommand}"]
        conman_args.extend(container_labels)

        # if args.subcommand is run add LLAMA_PROMPT_PREFIX to the container
        if hasattr(args, "subcommand") and args.subcommand == "run":
            # if podman
            if os.path.basename(args.engine) == "podman":
                conman_args += ["--env", "LLAMA_PROMPT_PREFIX=🦭 > "]
            elif os.path.basename(args.engine) == "docker":
                conman_args += ["--env", "LLAMA_PROMPT_PREFIX=🐋 > "]

        if os.path.basename(args.engine) == "podman" and args.podman_keep_groups:
            conman_args += ["--group-add", "keep-groups"]

        if os.path.basename(args.engine) == "docker" and args.pull == "newer":
            try:
                run_cmd([args.engine, "pull", "-q", args.image], ignore_all=True)
            except Exception:  # Ignore errors, the run command will handle it.
                pass
        else:
            conman_args += [f"--pull={args.pull}"]

        if sys.stdout.isatty() or sys.stdin.isatty():
            conman_args += ["-t"]

        if hasattr(args, "detach") and args.detach is True:
            conman_args += ["-d"]

        if hasattr(args, "port"):
            conman_args += ["-p", f"{args.port}:{args.port}"]

        if args.device:
            for device_arg in args.device:
                conman_args += ["--device", device_arg]
        else:
            if (sys.platform == "darwin" and os.path.basename(args.engine) != "docker") or os.path.exists("/dev/dri"):
                conman_args += ["--device", "/dev/dri"]

            if os.path.exists("/dev/kfd"):
                conman_args += ["--device", "/dev/kfd"]

            for k, v in get_env_vars().items():
                # Special case for Cuda
                if k == "CUDA_VISIBLE_DEVICES":
                    conman_args += ["--device", "nvidia.com/gpu=all"]
                conman_args += ["-e", f"{k}={v}"]
        if args.network != "":
            conman_args += ["--network", args.network]
        return conman_args

    def gpu_args(self, args, runner=False):
        gpu_args = []
        machine = platform.machine()
        if (
            os.getenv("HIP_VISIBLE_DEVICES")
            or os.getenv("ASAHI_VISIBLE_DEVICES")
            or os.getenv("CUDA_VISIBLE_DEVICES")
            or os.getenv("INTEL_VISIBLE_DEVICES")
            or (
                # linux and macOS report aarch64 differently, on Apple Silicon
                # (arm64), we should have acceleration on regardless.
                machine == "arm64"
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

        # Make sure Image precedes cmd_args.
        conman_args += [self._image(args)] + cmd_args

        if args.dryrun:
            dry_run(conman_args)
            return True

        exec_cmd(conman_args, debug=args.debug)
        return True

    def bench(self, args):
        self.validate_args(args)
        model_path = self.get_model_path(args)
        exec_args = self.build_exec_args_bench(args, model_path)
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

        get_gpu()
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

        get_gpu()
        gpu_args = self.gpu_args(args=args)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

        exec_args += ["-m", exec_model_path]

        return exec_args

    def build_exec_args_run(self, args, model_path, prompt):
        exec_model_path = model_path if not args.container else MNT_FILE

        # override prompt if not set to the local call
        if "LLAMA_PROMPT_PREFIX" not in os.environ:
            os.environ["LLAMA_PROMPT_PREFIX"] = "🦙 > "

        exec_args = ["llama-run", "-c", f"{args.context}", "--temp", f"{args.temp}"]

        if args.seed:
            exec_args += ["--seed", args.seed]

        if args.debug:
            exec_args += ["-v"]

        get_gpu()
        gpu_args = self.gpu_args(args=args, runner=True)
        if gpu_args is not None:
            exec_args.extend(gpu_args)

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

    def build_exec_args_serve(self, args, exec_model_path):
        if args.runtime == "vllm":
            exec_args = [
                "--model",
                exec_model_path,
                "--port",
                args.port,
                "--max-sequence-length",
                f"{args.context}",
            ]
        else:
            exec_args = [
                "llama-server",
                "--port",
                args.port,
                "-m",
                exec_model_path,
                "-c",
                f"{args.context}",
                "--temp",
                f"{args.temp}",
            ]
        if args.seed:
            exec_args += ["--seed", args.seed]

        return exec_args

    def handle_runtime(self, args, exec_args, exec_model_path):
        if args.runtime == "vllm":
            get_gpu()
            exec_model_path = os.path.dirname(exec_model_path)
            # Left out "vllm", "serve" the image entrypoint already starts it
            exec_args = ["--port", args.port, "--model", MNT_FILE, "--max_model_len", "2048"]
        else:
            get_gpu()
            gpu_args = self.gpu_args(args=args)
            if gpu_args is not None:
                exec_args.extend(gpu_args)
            exec_args.extend(["--host", args.host])
        return exec_args

    def generate_container_config(self, model_path, args, exec_args):
        self.image = self._image(args)
        if args.generate == "quadlet":
            self.quadlet(model_path, args, exec_args)
        elif args.generate == "kube":
            self.kube(model_path, args, exec_args)
        elif args.generate == "quadlet/kube":
            self.quadlet_kube(model_path, args, exec_args)
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

    def serve(self, args):
        self.validate_args(args)
        model_path = self.get_model_path(args)
        exec_model_path = MNT_FILE
        if not args.container and not args.generate:
            exec_model_path = model_path

        exec_args = self.build_exec_args_serve(args, exec_model_path)
        exec_args = self.handle_runtime(args, exec_args, exec_model_path)
        if self.generate_container_config(model_path, args, exec_args):
            return

        self.execute_command(model_path, exec_args, args)

    def quadlet(self, model, args, exec_args):
        quadlet = Quadlet(model, self.image, args, exec_args)
        quadlet.generate()

    def quadlet_kube(self, model, args, exec_args):
        kube = Kube(model, self.image, args, exec_args)
        kube.generate()
        quadlet = Quadlet(model, self.image, args, exec_args)
        quadlet.kube()

    def kube(self, model, args, exec_args):
        kube = Kube(model, self.image, args, exec_args)
        kube.generate()

    def path(self, args):
        return self.model_path(args)

    def model_path(self, args):
        return os.path.join(args.store, "models", self.type, self.directory, self.filename)

    def exists(self, args):
        model_path = self.model_path(args)
        if not os.path.exists(model_path):
            return None

        return model_path

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


def rm_until_substring(model, substring):
    pos = model.find(substring)
    if pos == -1:
        return model

    # Create a new string starting after the found substring
    return ''.join(model[i] for i in range(pos + len(substring), len(model)))
