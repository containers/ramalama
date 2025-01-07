import os
import sys
import atexit
import shlex

from ramalama.common import (
    container_manager,
    default_image,
    exec_cmd,
    find_working_directory,
    genname,
    run_cmd,
    get_gpu,
    get_env_vars,
)
from ramalama.version import version
from ramalama.quadlet import Quadlet
from ramalama.kube import Kube
from ramalama.common import mnt_dir, mnt_file

model_types = ["file", "https", "http", "oci", "huggingface", "hf", "ollama"]


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


class Model:
    """Model super class"""

    model = ""
    type = "Model"

    def __init__(self, model):
        self.model = model

    def login(self, args):
        raise NotImplementedError(f"ramalama login for {self.type} not implemented")

    def logout(self, args):
        raise NotImplementedError(f"ramalama logout for {self.type} not implemented")

    def pull(self, args):
        raise NotImplementedError(f"ramalama pull for {self.type} not implemented")

    def push(self, source, args):
        raise NotImplementedError(f"ramalama push for {self.type} not implemented")

    def is_symlink_to(self, file_path, target_path):
        if os.path.islink(file_path):
            symlink_target = os.readlink(file_path)
            abs_symlink_target = os.path.abspath(os.path.join(os.path.dirname(file_path), symlink_target))
            abs_target_path = os.path.abspath(target_path)
            return abs_symlink_target == abs_target_path

        return False

    def garbage_collection(self, args):
        for repo in model_types:
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

        return False

    def _image(self, args):
        if args.image != default_image():
            return args.image

        gpu_type, _ = get_gpu()
        if args.runtime == "vllm":
            if gpu_type == "HIP_VISIBLE_DEVICES":
                return "quay.io/modh/vllm:rhoai-2.17-rocm"

            return "quay.io/modh/vllm:rhoai-2.17-cuda"

        vers = version()
        conman = container_manager()
        images = {
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
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
            "RAMALAMA",
            "--security-opt=label=disable",
            "--name",
            name,
        ]

        if os.path.basename(args.engine) == "podman":
            conman_args += ["--pull=newer"]

        if sys.stdout.isatty() or sys.stdin.isatty():
            conman_args += ["-t"]

        if hasattr(args, "detach") and args.detach is True:
            conman_args += ["-d"]

        if hasattr(args, "port"):
            conman_args += ["-p", f"{args.port}:{args.port}"]

        if sys.platform == "darwin" or os.path.exists("/dev/dri"):
            conman_args += ["--device", "/dev/dri"]

        if os.path.exists("/dev/kfd"):
            conman_args += ["--device", "/dev/kfd"]

        for k, v in get_env_vars().items():
            conman_args += ["-e", f"{k}={v}"]

        return conman_args

    def run_container(self, args, shortnames):
        conman_args = self.setup_container(args)
        if len(conman_args) == 0:
            return False

        short_file = shortnames.create_shortname_file()
        wd = find_working_directory()

        conman_args += [
            f"-v{args.store}:/var/lib/ramalama",
            f"-v{os.path.realpath(sys.argv[0])}:/usr/bin/ramalama:ro",
            f"-v{wd}:/usr/share/ramalama/ramalama:ro",
            f"-v{short_file}:/usr/share/ramalama/shortnames.conf:ro,Z",
            "-e",
            "RAMALAMA_TRANSPORT",
        ]

        di_volume = distinfo_volume()
        if di_volume != "":
            conman_args += [di_volume]

        conman_args += [self._image(args)]
        conman_args += ["python3", "/usr/bin/ramalama"]
        conman_args += sys.argv[1:]
        if hasattr(args, "UNRESOLVED_MODEL"):
            index = conman_args.index(args.UNRESOLVED_MODEL)
            conman_args[index] = args.MODEL

        if args.dryrun:
            dry_run(conman_args)
            return True

        def cleanup():
            os.remove(short_file)

        atexit.register(cleanup)

        run_cmd(conman_args, stdout=None, debug=args.debug)
        return True

    def gpu_args(self):
        gpu_args = []
        if sys.platform == "darwin":
            # llama.cpp will default to the Metal backend on macOS, so we don't need
            # any additional arguments.
            pass
        elif sys.platform == "linux" and (
            os.getenv("HIP_VISIBLE_DEVICES") or os.getenv("ASAHI_VISIBLE_DEVICES") or os.getenv("CUDA_VISIBLE_DEVICES")
        ):
            gpu_args = ["-ngl", "99"]
        else:
            print("GPU offload was requested but is not available on this system")

        return gpu_args

    def exec_model_in_container(self, model_path, cmd_args, args):
        if not args.container:
            return False
        conman_args = self.setup_container(args)
        if len(conman_args) == 0:
            return False

        if model_path and os.path.exists(model_path):
            conman_args += [f"--mount=type=bind,src={model_path},destination={mnt_file},rw=false"]
        else:
            conman_args += [f"--mount=type=image,src={self.model},destination={mnt_dir},rw=false,subpath=/models"]

        # Make sure Image precedes cmd_args.
        conman_args += [self._image(args)]
        cargs = shlex.join(cmd_args)
        conman_args += ["/bin/sh", "-c", cargs]

        if args.dryrun:
            dry_run(conman_args)
            return True

        run_cmd(conman_args, debug=args.debug)
        return True

    def run(self, args):
        if hasattr(args, "name") and args.name:
            if not args.container:
                raise KeyError("--nocontainer and --name options conflict. --name requires a container.")

        prompt = ""
        if args.ARGS:
            prompt = " ".join(args.ARGS)

        # Build a prompt with the stdin text that prepend the prompt passed as
        # an argument to ramalama cli
        if not sys.stdin.isatty():
            inp = sys.stdin.read()
            prompt = inp + "\n\n" + prompt

        if args.dryrun:
            model_path = "/path/to/model"
        else:
            model_path = self.exists(args)
            if not model_path:
                model_path = self.pull(args)

        exec_model_path = mnt_file
        if not args.container:
            exec_model_path = model_path

        exec_args = ["llama-run", "-c", f"{args.context}", "--temp", f"{args.temp}"]

        if args.seed:
            exec_args += ["--seed", args.seed]

        if args.debug:
            exec_args += ["-v"]

        if args.gpu:
            exec_args.extend(self.gpu_args())

        exec_args += [
            exec_model_path,
            prompt,
        ]

        try:
            if self.exec_model_in_container(model_path, exec_args, args):
                return
            if args.dryrun:
                dry_run(exec_args)
                return
            exec_cmd(exec_args, args.debug, debug=args.debug)
        except FileNotFoundError as e:
            if args.container:
                raise NotImplementedError(
                    file_not_found_in_container % {"cmd": exec_args[0], "error": str(e).strip("'")}
                )
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def serve(self, args):
        if hasattr(args, "name") and args.name:
            if not args.container and not args.generate:
                raise KeyError("--nocontainer and --name options conflict. --name requires a container.")

        if args.dryrun:
            model_path = "/path/to/model"
        else:
            model_path = self.exists(args)
            if not model_path:
                model_path = self.pull(args)

        exec_model_path = mnt_file
        if not args.container and not args.generate:
            exec_model_path = model_path

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

        if args.runtime == "vllm":
            exec_model_path = os.path.dirname(exec_model_path)
            exec_args = ["vllm", "serve", "--port", args.port, exec_model_path]
        else:
            if args.gpu:
                exec_args.extend(self.gpu_args())
            exec_args.extend(["--host", args.host])

        if args.generate == "quadlet":
            return self.quadlet(model_path, args, exec_args)

        if args.generate == "kube":
            return self.kube(model_path, args, exec_args)

        if args.generate == "quadlet/kube":
            return self.quadlet_kube(model_path, args, exec_args)

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

    def quadlet(self, model, args, exec_args):
        quadlet = Quadlet(model, args, exec_args)
        quadlet.generate()

    def quadlet_kube(self, model, args, exec_args):
        kube = Kube(model, args, exec_args)
        kube.generate()
        quadlet = Quadlet(model, args, exec_args)
        quadlet.kube()

    def kube(self, model, args, exec_args):
        kube = Kube(model, args, exec_args)
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
