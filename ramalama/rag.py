import os
import subprocess
import tempfile
from functools import partial
from textwrap import dedent

from ramalama.chat import ChatOperationalArgs
from ramalama.common import accel_image, perror, set_accel_env_vars
from ramalama.compat import StrEnum
from ramalama.config import Config
from ramalama.engine import BuildEngine, Engine, is_healthy, stop_container, wait_for_healthy
from ramalama.path_utils import get_container_mount_path
from ramalama.transports.base import Transport
from ramalama.transports.oci import OCI

INPUT_DIR = "/docs"


class VectorDBEngine(Engine):
    """Generate a RAG vector database from source content."""

    def __init__(self, args):
        super().__init__(args)
        self.add_user()

    def add_input(self, path: str) -> None:
        if os.path.exists(path):
            fpath = os.path.realpath(path)
            input_name = os.path.basename(fpath)
            self.add_volume(fpath, f"{INPUT_DIR}/{input_name}")
        else:
            raise ValueError(f"{path} does not exist")

    def add_user(self):
        if self.use_docker:
            # Run the command in the container with the same uid as the current user.
            # Otherwise the files written to the tempdir will be owned by root and
            # they will not be readable by the subsequent "docker build".
            # Note: geteuid() doesn't exist on Windows, but this is only needed on Unix
            if hasattr(os, 'geteuid'):
                self.add_args("--user", str(os.geteuid()))


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
                ragdb.cleanup()


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
            # Convert to container-friendly path format (handles Windows path conversion)
            rag = get_container_mount_path(self.args.rag)
            # Read-write is the default behaviour for bind mounts in both Docker and Podman
            self.add_args(f"--mount=type=bind,source={rag},destination=/rag/vector.db{self.relabel()}")
        else:
            # Image mounts default to read-only in Podman, so we need rw=true for write access
            # Docker does not support type=image mounts
            if self.use_podman:
                self.add_args(f"--mount=type=image,source={self.args.rag},destination=/rag,rw=true")
            else:
                # Docker falls back to using volumes or other mechanisms
                self.add_args(f"--mount=type=image,source={self.args.rag},destination=/rag")


class RagTransport(OCI):
    """Run a RAG proxy, dispatching to a backend LLM"""

    type: str = "Model+RAG"

    def __init__(self, imodel: Transport, cmd: list[str], args):
        super().__init__(args.rag, args.store, args.engine)
        self.imodel = imodel
        self.model_cmd = cmd
        if os.path.exists(args.rag):
            self.kind = RagSource.DB
        else:
            self.kind = RagSource.IMAGE

    def exists(self) -> bool:
        if self.kind is RagSource.DB:
            return os.path.exists(self.model)
        return super().exists()

    def new_engine(self, args):
        return RagEngine(args, sourcetype=self.kind)

    def setup_mounts(self, args):
        pass

    def chat_operational_args(self, args):
        return ChatOperationalArgs(name=args.model_args.name)

    def _handle_container_chat(self, args, pid):
        # Clear args.rag so RamaLamaShell doesn't treat it as local data for RAG context
        args.rag = None
        super()._handle_container_chat(args, pid)

    def serve(self, args, cmd: list[str]):
        args.model_args.name = self.imodel.get_container_name(args.model_args)
        process = self.imodel.serve_nonblocking(args.model_args, self.model_cmd)
        if not args.dryrun:
            if process and process.wait() != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    " ".join(self.model_cmd),
                )
        try:
            super().serve(args, cmd)
        finally:
            if getattr(args.model_args, "name", None):
                args.model_args.ignore = True
                stop_container(args.model_args, args.model_args.name, remove=True)

    def run(self, args, cmd: list[str]):
        args.model_args.name = self.imodel.get_container_name(args.model_args)
        process = self.imodel.serve_nonblocking(args.model_args, self.model_cmd)
        rag_process = self.serve_nonblocking(args, cmd)

        if args.dryrun:
            return

        if process and process.wait() != 0:
            raise subprocess.CalledProcessError(
                process.returncode,
                " ".join(self.model_cmd),
            )
        if rag_process and rag_process.wait() != 0:
            raise subprocess.CalledProcessError(
                rag_process.returncode,
                " ".join(cmd),
            )
        return self._connect_and_chat(args, rag_process)

    def wait_for_healthy(self, args):
        self.imodel.wait_for_healthy(args.model_args)
        wait_for_healthy(args, partial(is_healthy, model_name=f"{self.imodel.model_name}+rag"))
