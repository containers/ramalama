import os
import subprocess
import tempfile

from ramalama.common import accel_image, get_accel_env_vars, run_cmd, set_accel_env_vars
from ramalama.config import CONFIG


class Rag:
    model = ""
    target = ""

    def __init__(self, target):
        self.target = target
        set_accel_env_vars()

    def build(self, source, target, contextdir, args):
        print(f"Building {target}...")
        src = os.path.basename(source)
        print(f"adding {src}...")
        cfile = f"""\
FROM scratch
COPY {src} /vector.db
"""
        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=True)
        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(cfile)
        imageid = (
            run_cmd(
                [
                    args.engine,
                    "build",
                    "--no-cache",
                    f"--network={args.network}",
                    "-q",
                    "-t",
                    target,
                    "-f",
                    containerfile.name,
                    contextdir,
                ],
                debug=args.debug,
            )
            .stdout.decode("utf-8")
            .strip()
        )
        return imageid

    def generate(self, args):
        args.image = accel_image(CONFIG, args)

        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")

        # Default image with "-rag" append is used for building rag data.
        s = args.image.split(":")
        s[0] = s[0] + "-rag"
        rag_image = ":".join(s)

        exec_args = [args.engine, "run", "--rm"]
        if args.network != "":
            exec_args += ["--network", args.network]
        for path in args.PATH:
            if os.path.exists(path):
                fpath = os.path.realpath(path)
                rpath = os.path.relpath(path)
                exec_args += ["-v", f"{fpath}:/docs/{rpath}:ro,z"]
        ragdb = tempfile.TemporaryDirectory(dir="/var/tmp/", prefix='RamaLama_rag_', delete=True)
        vectordb = tempfile.TemporaryDirectory(dir=ragdb.name, prefix='RamaLama_rag_', delete=True)
        exec_args += ["-v", f"{vectordb.name}:{vectordb.name}:z"]
        for k, v in get_accel_env_vars().items():
            # Special case for Cuda
            if k == "CUDA_VISIBLE_DEVICES":
                if os.path.basename(args.engine) == "docker":
                    exec_args += ["--gpus", "all"]
                else:
                    # newer Podman versions support --gpus=all, but < 5.0 do not
                    exec_args += ["--device", "nvidia.com/gpu=all"]

            exec_args += ["-e", f"{k}={v}"]

        exec_args += [rag_image]
        exec_args += ["doc2rag", vectordb.name, "/docs/"]
        try:
            run_cmd(exec_args, debug=args.debug)
        except subprocess.CalledProcessError as e:
            raise e

        print(self.build(vectordb.name, self.target, ragdb.name, args))
