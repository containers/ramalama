import os
import shutil
import subprocess
import tempfile

from ramalama.command.factory import assemble_command
from ramalama.common import accel_image, perror, run_cmd, set_accel_env_vars
from ramalama.config import Config
from ramalama.engine import Engine
from ramalama.logger import logger

INPUT_DIR = "/docs"


class VectorDBEngine(Engine):
    """Generate a RAG vector database from source content."""

    def __init__(self, args):
        super().__init__(args)

    def add_input(self, path: str) -> None:
        if os.path.exists(path):
            fpath = os.path.realpath(path)
            input_name = os.path.basename(fpath)
            self.add_volume(fpath, f"{INPUT_DIR}/{input_name}")
        else:
            raise ValueError(f"{path} does not exist")


class Rag:
    target: str = ""

    def __init__(self, target: str):
        if not target.islower():
            raise ValueError(f"invalid reference format: repository name '{target}' must be lowercase")
        self.target = target
        set_accel_env_vars()

    def build(self, source: str, target: str, args):
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

    def generate(self, args):
        args.nocapdrop = True
        args.inputdir = INPUT_DIR
        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")
        self.engine = VectorDBEngine(args)

        for path in args.PATHS:
            self.engine.add_input(path)

        target_is_oci = self.target.startswith("oci://") or (
            not self.target.startswith("file://") and self.target[0] not in {".", "/"}
        )
        if target_is_oci:
            ragdb = tempfile.TemporaryDirectory(prefix="RamaLama_rag_")
            dbdir = os.path.join(ragdb.name, "vectordb")
            os.makedirs(dbdir)
        else:
            dbdir = self.target

        self.engine.add_volume(f"{dbdir}", "/output", opts="rw")
        self.engine.add_args(args.image)
        self.engine.add_args(*assemble_command(args))
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


def rag_image(config: Config) -> str:
    return accel_image(config, images=config.rag_images, conf_key="rag_image")
