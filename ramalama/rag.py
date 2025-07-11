import os
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

from ramalama.common import get_accel_env_vars, perror, run_cmd, set_accel_env_vars
from ramalama.engine import Engine
from ramalama.logger import logger

INPUT_DIR = "/docs"


class Rag:
    model = ""
    target = ""
    urls = []

    def __init__(self, target):
        if not target.islower():
            raise ValueError(f"invalid reference format: repository name '{target}' must be lowercase")
        self.target = target
        set_accel_env_vars()

    def build(self, source, target, args):
        perror(f"\nBuilding {target} ...")
        contextdir = os.path.dirname(source)
        src = os.path.basename(source)
        perror(f"adding {src} ...")
        cfile = f"""\
FROM scratch
COPY {src} /vector.db
"""
        containerfile = tempfile.NamedTemporaryFile(dir=source)
        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(cfile)
            c.flush()

        logger.debug(f"\nContainerfile: {containerfile.name}\n{cfile}")

        exec_args = [
            args.engine,
            "build",
            "--no-cache",
            "--network=none",
            "-q",
            "-t",
            target,
            "-f",
            containerfile.name,
            contextdir,
        ]
        imageid = (
            run_cmd(
                exec_args,
            )
            .stdout.decode("utf-8")
            .strip()
        )
        return imageid

    def _handle_paths(self, path):
        """Adds a volume mount if path exists, otherwise add URL."""
        parsed = urlparse(path)
        if parsed.scheme in ["file", ""] and parsed.netloc == "":
            if os.path.exists(parsed.path):
                fpath = os.path.realpath(parsed.path)
                self.engine.add(["-v", f"{fpath}:{INPUT_DIR}/{fpath}:ro,z"])
            else:
                raise ValueError(f"{path} does not exist")
            return
        self.urls.append(path)

    def generate(self, args):
        args.nocapdrop = True
        self.engine = Engine(args)
        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")

        tmpdir = "."
        if not os.access(tmpdir, os.W_OK):
            tmpdir = "/tmp"

        for path in args.PATH:
            self._handle_paths(path)

        # If user specifies path, then don't use it

        target_is_oci = self.target.startswith("oci://") or (
            not self.target.startswith("file://") and self.target[0] not in {".", "/"}
        )
        if target_is_oci:
            ragdb = tempfile.TemporaryDirectory(dir=tmpdir, prefix='RamaLama_rag_')
            dbdir = os.path.join(ragdb.name, "vectordb")
        else:
            dbdir = self.target

        os.makedirs(dbdir, exist_ok=True)
        self.engine.add(["-v", f"{dbdir}:/output:z"])
        for k, v in get_accel_env_vars().items():
            # Special case for Cuda
            if k == "CUDA_VISIBLE_DEVICES":
                if os.path.basename(args.engine) == "docker":
                    self.engine.add(["--gpus", "all"])
                else:
                    # newer Podman versions support --gpus=all, but < 5.0 do not
                    self.engine.add(["--device", "nvidia.com/gpu=all"])
            elif k == "MUSA_VISIBLE_DEVICES":
                self.exec_args += ["--env", "MTHREADS_VISIBLE_DEVICES=all"]

            self.engine.add(["-e", f"{k}={v}"])

        self.engine.add([rag_image(args.image)])
        self.engine.add(["doc2rag", "--format", args.format, "/output", INPUT_DIR])
        if args.ocr:
            self.engine.add(["--ocr"])
        if len(self.urls) > 0:
            self.engine.add(self.urls)
        if args.dryrun:
            self.engine.dryrun()
            return
        try:
            self.engine.run()
            if target_is_oci:
                print(self.build(dbdir, self.target, args))
        except subprocess.CalledProcessError as e:
            raise e
        finally:
            if target_is_oci:
                shutil.rmtree(ragdb.name, ignore_errors=True)


def rag_image(image) -> str:
    imagespec = image.split(":")
    rag_image = f"{imagespec[0]}-rag"
    if len(imagespec) > 1:
        rag_image = f"{rag_image}:{imagespec[1]}"
    return rag_image
