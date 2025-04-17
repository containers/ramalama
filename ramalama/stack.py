import glob
import os
import sys

import ramalama
from ramalama.common import check_nvidia, exec_cmd, genname, get_accel_env_vars

USE_RAMALAMA_WRAPPER = False

file_not_found = """\
RamaLama requires the "%(cmd)s" command to be installed on the host when running with --nocontainer.
RamaLama is designed to run AI Models inside of containers, where "%(cmd)s" is already installed.
Either install a package containing the "%(cmd)s" command or run the workload inside of a container.
%(error)s"""


class StackBase:

    def __not_implemented_error(self, param):
        return NotImplementedError(f"ramalama {param} for '{type(self).__name__}' not implemented")

    def pull(self, args):
        raise self.__not_implemented_error("pull")

    def run(self, args):
        raise self.__not_implemented_error("serve")


class Stack(StackBase):
    """Stack super class"""

    distro = ""
    type = "Distro"

    def __init__(self, distro):
        self.distro = distro

        split = self.distro.rsplit("/", 1)
        self.directory = split[0] if len(split) > 1 else ""
        self.filename = split[1] if len(split) > 1 else split[0]

        self._distro_name: str
        self._distro_tag: str
        self._distro_organization: str
        self._distro_type: str
        self._distro_name, self._distro_tag, self._distro_organization = self.extract_distro_identifiers()
        self._distro_type = type(self).__name__.lower()

    def extract_distro_identifiers(self):
        distro_name = self.distro
        distro_tag = "latest"
        distro_organization = ""

        # extract distro tag from name if exists
        if ":" in distro_name:
            distro_name, distro_tag = distro_name.split(":", 1)

        # extract distro organization from name if exists and update name
        split = distro_name.rsplit("/", 1)
        distro_organization = split[0].removeprefix("/") if len(split) > 1 else ""
        distro_name = split[1] if len(split) > 1 else split[0]

        return distro_name, distro_tag, distro_organization

    @property
    def name(self) -> str:
        return self._distro_name

    @property
    def tag(self) -> str:
        return self._distro_tag

    @property
    def organization(self) -> str:
        return self._distro_organization

    @property
    def distro_type(self) -> str:
        return self._distro_type

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

    def handle_podman_specifics(self, conman_args, args):
        if os.path.basename(args.engine) == "podman" and args.podman_keep_groups:
            conman_args += ["--group-add", "keep-groups"]

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

    def exists(self, args):
        distro_path = self.distro_path(args)
        if not os.path.exists(distro_path):
            return None

        return distro_path

    def get_distro_path(self, args):
        distro_path = self.exists(args)
        if distro_path:
            return distro_path

        if args.dryrun:
            return "/path/to/distro"

        distro_path = self.pull(args)

        return distro_path

    def get_distro_registry(self, args):
        distro_path = self.get_distro_path(args)
        if not distro_path or args.dryrun:
            return ""

        parts = distro_path.replace(args.store, "").split(os.sep)
        if len(parts) < 3:
            return ""
        return parts[2]

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

    def build_exec_args_run(self, args, distro_path):
        exec_args = []
        if USE_RAMALAMA_WRAPPER:
            exec_args += ["ramalama-serve-core"]

        exec_args += [
            f"CONTAINER_BINARY={args.engine}" "llama",
            "stack",
            "run",
            distro_path,
            "--image-type",
            "container",
        ] + args.runtime_args

        return exec_args

    def execute_command(self, distro_path, exec_args, args):
        try:
            if args.dryrun:
                dry_run(exec_args)
                return
            exec_cmd(exec_args, debug=args.debug)
        except FileNotFoundError as e:
            raise NotImplementedError(file_not_found % {"cmd": exec_args[0], "error": str(e).strip("'")})

    def run(self, args):
        self.validate_args(args)
        distro_path = self.get_distro_path(args)
        exec_args = self.build_exec_args_run(args, distro_path)
        self.execute_command(distro_path, exec_args, args)


def dry_run(args):
    for arg in args:
        if not arg:
            continue
        if " " in arg:
            print('"%s"' % arg, end=" ")
        else:
            print("%s" % arg, end=" ")
    print()
