import os
import sys
import glob
import atexit

from ramalama.common import (
    default_image,
    exec_cmd,
    find_working_directory,
    genname,
    in_container,
    run_cmd,
)
from ramalama.version import version


file_not_found = """\
RamaLama requires the "%s" command to be installed on the host when running with --nocontainer.
RamaLama is designed to run AI Models inside of containers, where "%s" is already installed.
Either install a package containing the "%s" command or run the workload inside of a container.
"""

file_not_found_in_container = """\
RamaLama requires the "%s" command to be installed inside of the container.
RamaLama requires the server application be installed in the container images.
Either install a package containing the "%s" command in the container or run
with the default RamaLama image.
"""


class Model:
    """Model super class"""

    model = ""
    type = "Model"
    common_params = ["-c", "2048"]

    def __init__(self, model):
        self.model = model

    def login(self, args):
        raise NotImplementedError(f"ramalama login for {self.type} not implemented")

    def logout(self, args):
        raise NotImplementedError(f"ramalama logout for {self.type} not implemented")

    def path(self, source, args):
        raise NotImplementedError(f"ramalama path for {self.type} not implemented")

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
        repo_paths = ["huggingface", "oci", "ollama"]
        for repo in repo_paths:
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
        if os.path.exists(model_path):
            try:
                os.remove(model_path)
                print(f"Untagged: {self.model}")
            except OSError as e:
                if not args.ignore:
                    raise KeyError(f"removing {self.model}: {e}")
        else:
            if not args.ignore:
                raise KeyError(f"model {self.model} not found")

        self.garbage_collection(args)

    def model_path(self, args):
        raise NotImplementedError(f"model_path for {self.type} not implemented")

    # Add paths if they exist
    def add_volume(self, conman_args, path):
        if os.path.exists(path):
            conman_args.append(f"-v{path}:{path}:ro")

        return conman_args

    def run_container(self, args, shortnames):
        conman = args.engine
        if conman == "":
            return False

        short_file = shortnames.create_shortname_file()
        name = self.get_container_name(args)
        conman_args = self.initialize_conman_args(conman, args, name, short_file)

        conman_args = self.add_volumes(conman_args, args, short_file)
        conman_args = self.add_runtime_options(conman_args, args)
        conman_args = self.configure_gpu(conman_args, args)
        conman_args += ["python3", "/usr/bin/ramalama"]
        conman_args += sys.argv[1:]
        if hasattr(args, "UNRESOLVED_MODEL"):
            index = conman_args.index(args.UNRESOLVED_MODEL)
            conman_args[index] = args.MODEL

        if args.dryrun:
            dry_run(conman_args)
            return True

        atexit.register(self.cleanup_short_file, short_file)
        run_cmd(conman_args, stdout=None, debug=args.debug)
        return True

    def get_container_name(self, args):
        if hasattr(args, "name") and args.name:
            return args.name
        return genname()

    def initialize_conman_args(self, conman, args, name, short_file):
        wd = find_working_directory()
        conman_args = [
            conman,
            "run",
            "--rm",
            "-i",
            "--label",
            "RAMALAMA",
            "--security-opt=label=disable",
            "-e",
            "RAMALAMA_TRANSPORT",
            "--name",
            name,
            f"-v{args.store}:/var/lib/ramalama",
            f"-v{os.path.realpath(sys.argv[0])}:/usr/bin/ramalama:ro",
            f"-v{short_file}:/usr/share/ramalama/shortnames.conf:ro,Z",
            f"-v{wd}:/usr/share/ramalama/ramalama:ro",
        ]
        return conman_args

    def add_volumes(self, conman_args, args, short_file):
        # Add standard volumes
        conman_args = self.add_volume(conman_args, "/usr/share/ramalama/ramalama.conf")
        conman_args = self.add_volume(conman_args, "/usr/share/ramalama/ramalama.conf.d")
        conman_args = self.add_volume(conman_args, "/etc/ramalama")
        # Add user configuration if it exists
        path_to_share = os.path.expanduser("~/.config/ramalama")
        if os.path.exists(path_to_share):
            conman_args.append(f"-v{path_to_share}:/root/.config/ramalama:ro")
        # Add distribution information volume if available
        di_volume = distinfo_volume()
        if di_volume:
            conman_args.append(di_volume)

        return conman_args

    def configure_gpu(self, conman_args, args):
        # Configure GPU if detected
        gpu_type, gpu_num = get_gpu()
        if gpu_type == "HIP_VISIBLE_DEVICES":
            conman_args.extend(["-e", f"{gpu_type}={gpu_num}"])
            image = args.image if args.image != default_image() else "quay.io/ramalama/rocm:latest"
            conman_args.append(image)
        else:
            conman_args.append(args.image)

        return conman_args

    def add_runtime_options(self, conman_args, args):
        # Add options like ports, devices, and TTY based on runtime environment
        if sys.stdout.isatty() and sys.stdin.isatty():
            conman_args.append("-t")
        if hasattr(args, "detach") and args.detach:
            conman_args.append("-d")
        if hasattr(args, "port"):
            conman_args.extend(["-p", f"{args.port}:{args.port}"])
        if sys.platform == "darwin" or os.path.exists("/dev/dri"):
            conman_args.extend(["--device", "/dev/dri"])
        if os.path.exists("/dev/kfd"):
            conman_args.extend(["--device", "/dev/kfd"])

        return conman_args

    def cleanup_short_file(self, short_file):
        os.remove(short_file)

    def gpu_args(self):
        gpu_args = []
        if sys.platform == "darwin":
            # llama.cpp will default to the Metal backend on macOS, so we don't need
            # any additional arguments.
            pass
        elif sys.platform == "linux" and (
            os.path.exists("/dev/dri") or os.getenv("HIP_VISIBLE_DEVICES") or os.getenv("CUDA_VISIBLE_DEVICES")
        ):
            gpu_args = ["-ngl", "99"]
        else:
            print("GPU offload was requested but is not available on this system")

        return gpu_args

    def run(self, args):
        prompt = "You are a helpful assistant"
        if args.ARGS:
            prompt = " ".join(args.ARGS)

        # Build a prompt with the stdin text that prepend the prompt passed as
        # an argument to ramalama cli
        if not sys.stdin.isatty():
            input = sys.stdin.read()
            prompt = input + "\n\n" + prompt

        model_path = self.pull(args)
        exec_args = ["llama-cli", "-m", model_path, "--in-prefix", "", "--in-suffix", ""]

        if not args.debug:
            exec_args += ["--no-display-prompt"]

        exec_args += [
            "-p",
            prompt,
        ] + self.common_params

        if not args.ARGS and sys.stdin.isatty():
            exec_args.append("-cnv")

        if args.gpu:
            exec_args.extend(self.gpu_args())

        try:
            exec_cmd(exec_args, args.debug, debug=args.debug)
        except FileNotFoundError as e:
            if in_container():
                raise NotImplementedError(file_not_found_in_container % (exec_args[0], str(e).strip("'")))
            raise NotImplementedError(file_not_found % (exec_args[0], exec_args[0], exec_args[0], str(e).strip("'")))

    def serve(self, args):
        model_path = self.pull(args)
        exec_args = ["llama-server", "--port", args.port, "-m", model_path]
        if args.runtime == "vllm":
            exec_args = ["vllm", "serve", "--port", args.port, model_path]
        else:
            if args.gpu:
                exec_args.extend(self.gpu_args())
            if in_container():
                exec_args.extend(["--host", "0.0.0.0"])

        if args.generate == "quadlet":
            return self.quadlet(model_path, args, exec_args)

        if args.generate == "kube":
            return self.kube(model_path, args, exec_args)

        try:
            exec_cmd(exec_args, debug=args.debug)
        except FileNotFoundError as e:
            if in_container():
                raise NotImplementedError(file_not_found_in_container % (exec_args[0], str(e).strip("'")))
            raise NotImplementedError(file_not_found % (exec_args[0], exec_args[0], exec_args[0], str(e).strip("'")))

    def quadlet(self, model, args, exec_args):
        port_string = ""
        if hasattr(args, "port"):
            port_string = f"PublishPort={args.port}"

        name_string = ""
        if hasattr(args, "name") and args.name:
            name_string = f"ContainerName={args.name}"

        print(
            f"""
[Unit]
Description=RamaLama {args.UNRESOLVED_MODEL} AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec={" ".join(exec_args)}
Image={default_image()}
Volume={model}:/run/model:ro,z
{name_string}
{port_string}

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
"""
        )

    def _gen_ports(self, args):
        if not hasattr(args, "port"):
            return ""

        p = args.port.split(":", 2)
        ports = f"""\
    ports:
    - containerPort: {p[0]}"""
        if len(p) > 1:
            ports += f"""
      hostPort: {p[1]}"""

        return ports

    def _gen_volumes(self, model, args):
        mounts = """\
    volumeMounts:
    - mountPath: /run/model
      name: model"""

        volumes = f"""
  volumes:
  - name model
    hostPath:
      path: {model}"""

        for dev in ["dri", "kfd"]:
            if os.path.exists("/dev/" + dev):
                mounts = (
                    mounts
                    + f"""
    - mountPath: /dev/{dev}
      name: {dev}"""
                )
                volumes = (
                    volumes
                    + f""""
  - name {dev}
    hostPath:
      path: /dev/{dev}"""
                )

        return mounts + volumes

    def kube(self, model, args, exec_args):
        port_string = self._gen_ports(args)
        volume_string = self._gen_volumes(model, args)
        _version = version()
        if hasattr(args, "name") and args.name:
            name = args.name
        else:
            name = genname()

        print(
            f"""\
# Save the output of this file and use kubectl create -f to import
# it into Kubernetes.
#
# Created with ramalama-{_version}
apiVersion: v1
kind: Deployment
metadata:
  labels:
    app: {name}
  name: {name}
spec:
  containers:
  - name: {name}
    image: {args.image}
    command: ["{exec_args[0]}"]
    args: {exec_args[1:]}
{port_string}
{volume_string}"""
        )


def get_gpu():
    i = 0
    gpu_num = 0
    gpu_bytes = 0
    for fp in sorted(glob.glob('/sys/bus/pci/devices/*/mem_info_vram_total')):
        with open(fp, 'r') as file:
            content = int(file.read())
            if content > 1073741824 and content > gpu_bytes:
                gpu_bytes = content
                gpu_num = i

        i += 1

    if gpu_bytes:  # this is the ROCm/AMD case
        return "HIP_VISIBLE_DEVICES", gpu_num

    return None, None


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
