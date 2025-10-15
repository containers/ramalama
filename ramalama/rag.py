import os
import shutil
import subprocess
import tempfile
from textwrap import dedent

from ramalama.command.factory import assemble_command
from ramalama.common import accel_image, perror, set_accel_env_vars
from ramalama.config import Config
from ramalama.engine import BuildEngine, Engine

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
    oci: bool = False

    def __init__(self, target: str):
        self.target = target
        self.oci = self.target.startswith("oci://") or (
            not self.target.startswith("file://") and self.target[0] not in {".", "/"}
        )
        if self.oci and not self.target.islower():
            raise ValueError(f"invalid reference format: repository name '{self.target}' must be lowercase")
        set_accel_env_vars()

    def build(self, source: str, args):
        perror(f"Building {self.target} ...")
        contextdir = os.path.dirname(source)
        src = os.path.basename(source)
        engine = BuildEngine(args)
        return engine.build_containerfile(
            dedent(
                f"""
                FROM scratch
                COPY {src} /vector.db
                """
            ),
            contextdir,
            tag=self.target,
        )

    def generate(self, args):
        args.nocapdrop = True
        args.inputdir = INPUT_DIR
        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")
        engine = VectorDBEngine(args)

        for path in args.PATHS:
            engine.add_input(path)

        if self.oci:
            ragdb = tempfile.TemporaryDirectory(prefix="RamaLama_rag_")
            dbdir = os.path.join(ragdb.name, "vectordb")
            os.makedirs(dbdir)
        else:
            dbdir = self.target

        engine.add_volume(dbdir, "/output", opts="rw")
        engine.add_args(args.image)
        engine.add_args(*assemble_command(args))
        try:
            if args.dryrun:
                engine.dryrun()
            else:
                engine.run()
            if self.oci:
                print(self.build(dbdir, args))
        except subprocess.CalledProcessError as e:
            raise e
        finally:
            if self.oci:
                shutil.rmtree(ragdb.name, ignore_errors=True)


def rag_image(config: Config) -> str:
    return accel_image(config, images=config.rag_images, conf_key="rag_image")
