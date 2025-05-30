import glob
import json
import os
import subprocess
import sys

# Live reference for checking global vars
import ramalama.common
from ramalama.common import check_nvidia, exec_cmd, get_accel_env_vars, perror, run_cmd
from ramalama.console import EMOJI


class Engine:
    def __init__(self, args):
        self.exec_args = [
            args.engine,
            "run",
            "--rm",
        ]
        base = os.path.basename(args.engine)
        self.use_docker = base == "docker"
        self.use_podman = base == "podman"
        self.args = args
        self.add_labels()
        self.add_device_options()
        self.add_env_option()
        self.add_network()
        self.add_oci_runtime()
        self.add_port_option()
        self.add_privileged_options()
        self.add_pull_newer()
        self.add_rag()
        self.add_subcommand_env()
        self.add_tty_option()
        self.handle_podman_specifics()
        self.add_detach_option()

    def add_label(self, label):
        self.add(["--label", label])

    def add_name(self, name):
        self.add(["--name", name])

    def add_labels(self):
        add_labels(self.args, self.add_label)

    def add_pull_newer(self):
        if not self.args.dryrun and self.use_docker and self.args.pull == "newer":
            try:
                if not self.args.quiet:
                    print(f"Checking for newer image {self.args.image}")
                run_cmd([self.args.engine, "pull", "-q", self.args.image], ignore_all=True)
            except Exception:  # Ignore errors, the run command will handle it.
                pass
        else:
            self.exec_args += ["--pull", self.args.pull]

    def add_network(self):
        if hasattr(self.args, "network") and self.args.network:
            self.exec_args += ["--network", self.args.network]

    def add_oci_runtime(self):
        if hasattr(self.args, "oci_runtime") and self.args.oci_runtime:
            self.exec_args += ["--runtime", self.args.oci_runtime]
            return
        if check_nvidia() == "cuda":
            if self.use_docker:
                self.exec_args += ["--runtime", "nvidia"]
            elif os.access("/usr/bin/nvidia-container-runtime", os.X_OK):
                self.exec_args += ["--runtime", "/usr/bin/nvidia-container-runtime"]

    def add_privileged_options(self):
        if hasattr(self.args, "privileged") and self.args.privileged:
            self.exec_args += ["--privileged"]
        else:
            self.exec_args += [
                "--security-opt=label=disable",
            ]
            if not hasattr(self.args, "nocapdrop"):
                self.exec_args += [
                    "--cap-drop=all",
                    "--security-opt=no-new-privileges",
                ]

    def cap_add(self, cap):
        self.exec_args += ["--cap-add", cap]

    def add_subcommand_env(self):
        if EMOJI and hasattr(self.args, "subcommand") and self.args.subcommand == "run":
            if os.path.basename(self.args.engine) == "podman":
                self.exec_args += ["--env", "LLAMA_PROMPT_PREFIX=🦭 > "]
            if self.use_docker:
                self.exec_args += ["--env", "LLAMA_PROMPT_PREFIX=🐋 > "]

    def add_env_option(self):
        if hasattr(self.args, "env"):
            for env in self.args.env:
                self.exec_args += ["--env", env]

    def add_tty_option(self):
        if sys.stdout.isatty() or sys.stdin.isatty():
            self.exec_args += ["-t"]

    def add_detach_option(self):
        if hasattr(self.args, "detach") and self.args.detach is True:
            self.exec_args += ["-d"]

    def add_port_option(self):
        if not hasattr(self.args, "port") or not self.args.port or self.args.port == "":
            return

        if self.args.port.count(":") > 0:
            self.exec_args += ["-p", self.args.port]
        else:
            self.exec_args += ["-p", f"{self.args.port}:{self.args.port}"]

    def add_device_options(self):
        if hasattr(self.args, "device") and self.args.device:
            for device_arg in self.args.device:
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

    def add_rag(self):
        if not hasattr(self.args, "rag") or not self.args.rag:
            return

        if os.path.exists(self.args.rag):
            rag = os.path.realpath(self.args.rag)
            # Added temp read write because vector database requires write access even if nothing is written
            self.exec_args.append(f"--mount=type=bind,source={rag},destination=/rag/vector.db,rw=true")
        else:
            self.exec_args.append(f"--mount=type=image,source={self.args.rag},destination=/rag,rw=true")

    def handle_podman_specifics(self):
        if hasattr(self.args, "podman_keep_groups") and self.args.podman_keep_groups:
            self.exec_args += ["--group-add", "keep-groups"]

    def add(self, newargs):
        self.exec_args += newargs

    def dryrun(self):
        dry_run(self.exec_args)

    def run(self):
        run_cmd(self.exec_args)

    def exec(self):
        exec_cmd(self.exec_args)


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
    conman = args.engine
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "images"]
    if hasattr(args, "noheading") and args.noheading:
        conman_args += ["--noheading"]

    if hasattr(args, "notrunc") and args.notrunc:
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
    conman = args.engine
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "ps", "-a", "--filter", "label=ai.ramalama"]
    if hasattr(args, "noheading") and args.noheading:
        conman_args += ["--noheading"]

    if hasattr(args, "notrunc") and args.notrunc:
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


def info(args):
    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "info", "--format", "json"]
    try:
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return json.loads(output)
    except FileNotFoundError as e:
        return str(e)


def inspect(args, name, format=None, ignore_stderr=False):
    if not name:
        raise ValueError("must specify a container name")
    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "inspect"]
    if format:
        conman_args += ["--format", format]

    conman_args += [name]
    return run_cmd(conman_args, ignore_stderr=ignore_stderr, debug=args.debug).stdout.decode("utf-8").strip()


def stop_container(args, name):
    if not name:
        raise ValueError("must specify a container name")
    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    ignore_stderr = False
    pod = ""
    try:
        pod = inspect(args, name, format="{{ .Pod }}", ignore_stderr=True)
    except Exception:  # Ignore errors, the stop command will handle it.
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


def container_connection(args, name, port):
    if not name:
        raise ValueError("must specify a container name")
    if not port:
        raise ValueError("must specify a port to check")

    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "port", name, port]
    output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()
    return "" if output == "" else output.split(">")[-1].strip()


def add_labels(args, add_label):
    label_map = {
        "MODEL": "ai.ramalama.model",
        "engine": "ai.ramalama.engine",
        "runtime": "ai.ramalama.runtime",
        "port": "ai.ramalama.port",
        "subcommand": "ai.ramalama.command",
    }
    for arg, label_prefix in label_map.items():
        if hasattr(args, arg):
            if value := getattr(args, arg):
                add_label(f"{label_prefix}={value}")
