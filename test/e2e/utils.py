import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from test.conftest import ramalama_container, ramalama_container_engine


class RamalamaExecWorkspace:
    def __init__(
        self,
        isolated: bool = True,
        config: str = None,
        env_vars: dict = None,
        container_engine_discover=True,
        container_discover=True,
    ):
        self.isolated = isolated
        self.config = config
        self.environ = os.environ.copy()
        self.workspace_dir = tempfile.mkdtemp() if self.isolated or self.config else None
        self.storage_dir = None
        self.__prev_working_dir = None

        # Create ramalama.conf for the workspace if config is provided
        if self.workspace_dir and self.config:
            config_path = Path(self.workspace_dir) / "ramalama.conf"
            with config_path.open("w") as f:
                f.write(self.config.format(workspace_dir=self.workspace_dir))
                self.environ["RAMALAMA_CONFIG"] = config_path.as_posix()

        # Create storage directory
        if self.isolated or self.config:
            storage_dir = Path(self.workspace_dir) / ".storage"
            storage_dir.mkdir()
            self.storage_dir = storage_dir.as_posix()

        # Enable env variables from pytest addoption parameters
        if container_discover:
            self.environ["RAMALAMA_IN_CONTAINER"] = "True" if ramalama_container else "False"
        if container_engine_discover:
            self.environ["RAMALAMA_CONTAINER_ENGINE"] = ramalama_container_engine

        # Update the environ with the extra env vars provided if any
        if env_vars:
            self.environ |= env_vars

    def __enter__(self):
        self.__prev_working_dir = os.getcwd()
        os.chdir(self.workspace_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.__prev_working_dir)
        self.close()

    def close(self):
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir)

    def _prepare_kwargs(self, kwargs):
        env = self.environ.copy()
        if 'env' in kwargs:
            env |= kwargs['env']
        kwargs['env'] = env
        return kwargs

    def check_output(self, *args, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        return subprocess.check_output(*args, **kwargs).decode("utf-8")

    def check_call(self, *args, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        return subprocess.check_call(*args, **kwargs)


def check_output(*args, **kwargs):
    with RamalamaExecWorkspace() as ctx:
        return ctx.check_output(*args, **kwargs)


def check_call(*args, **kwargs):
    with RamalamaExecWorkspace() as ctx:
        return ctx.check_call(*args, **kwargs)
