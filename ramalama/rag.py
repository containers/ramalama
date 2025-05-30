import os
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

from ramalama.common import accel_image, get_accel_env_vars, run_cmd, set_accel_env_vars
from ramalama.config import CONFIG
from ramalama.engine import Engine
from ramalama.logger import logger


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
        print(f"\nBuilding {target} ...")
        contextdir = os.path.dirname(source)
        src = os.path.basename(source)
        print(f"adding {src} ...")
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
                self.engine.add(["-v", f"{fpath}:/docs/{fpath}:ro,z"])
            else:
                raise ValueError(f"{path} does not exist")
            return
        self.urls.append(path)

    def generate(self, args):
        args.nocapdrop = True
        self.engine = Engine(args)
        # force accel_image to use -rag version. Drop TAG if it exists
        # so that accel_image will add -rag to the image specification.
        args.rag = "rag"
        args.image = args.image.split(":")[0]
        args.image = accel_image(CONFIG, args)

        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")

        tmpdir = "."
        if not os.access(tmpdir, os.W_OK):
            tmpdir = "/tmp"

        for path in args.PATH:
            self._handle_paths(path)

        ragdb = tempfile.TemporaryDirectory(dir=tmpdir, prefix='RamaLama_rag_')
        dbdir = os.path.join(ragdb.name, "vectordb")
        os.mkdir(dbdir)
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

        self.engine.add([args.image])
        self.engine.add(["doc2rag", "/output", "/docs/"])
        if args.ocr:
            self.engine.add(["--ocr"])
        if len(self.urls) > 0:
            self.engine.add(self.urls)
        if args.dryrun:
            self.engine.dryrun()
            return
        try:
            self.engine.run()
            print(self.build(dbdir, self.target, args))
        except subprocess.CalledProcessError as e:
            raise e
        finally:
            shutil.rmtree(ragdb.name, ignore_errors=True)
