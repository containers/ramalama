import os
import shutil
import subprocess
import tempfile
from enum import StrEnum
from textwrap import dedent

from ramalama.chat import ChatOperationalArgs
from ramalama.common import accel_image, perror, set_accel_env_vars
from ramalama.config import Config
from ramalama.engine import BuildEngine, Engine
from ramalama.transports.base import Transport

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

    def generate(self, args, cmd):
        args.nocapdrop = True
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
        engine.add_args(*cmd)
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


class RagSource(StrEnum):
    DB = "db"
    IMAGE = "image"


class RagEngine(Engine):
    """Engine for executing a RAG proxy"""

    sourcetype: RagSource

    def __init__(self, args, /, *, sourcetype: RagSource):
        self.sourcetype = sourcetype
        super().__init__(args)
        self.add_rag()

    def add_labels(self):
        super().add_labels()
        self.add_label(f"ai.ramalama.rag.{self.sourcetype}={self.args.rag}")

    def add_rag(self):
        if self.sourcetype is RagSource.DB:
            rag = os.path.realpath(self.args.rag)
            # Added temp read write because vector database requires write access even if nothing is written
            self.add_args(f"--mount=type=bind,source={rag},destination=/rag/vector.db,rw=true{self.relabel()}")
        else:
            self.add_args(f"--mount=type=image,source={self.args.rag},destination=/rag,rw=true")


class RagTransport(Transport):
    """Run a RAG proxy, dispatching to a backend LLM"""

    type: str = "Model+RAG"

    def __init__(self, imodel: Transport, args, cmd: list[str], is_image: bool):
        super().__init__(args.rag, args.store)
        self.imodel = imodel
        self.args = args
        self.cmd = cmd
        if is_image:
            self.kind = RagSource.IMAGE
        else:
            self.kind = RagSource.DB

    def new_engine(self, args):
        return RagEngine(args, sourcetype=self.kind)

    def setup_mounts(self, args):
        pass

    def chat_operational_args(self, args):
        return ChatOperationalArgs(name=args.model_name)

    def _handle_container_chat(self, args, pid):
        # Clear args.rag so RamaLamaShell doesn't treat it as local data for RAG context
        self.args.rag = None
        super()._handle_container_chat(args, pid)

    def run(self, args, cmd: list[str]):
        self.model_args = args
        self.args.model_pid = self.imodel._fork_and_serve(args, cmd)
        self.args.model_name = self.imodel.get_container_name(args)
        if self.args.model_pid:
            if self.args.dryrun:
                # Avoid race condition in tests
                os.waitpid(self.args.model_pid, 0)
            super().run(self.args, self.cmd)

    def wait_for_healthy(self, args):
        self.imodel.wait_for_healthy(self.model_args)
        super().wait_for_healthy(self.args)
