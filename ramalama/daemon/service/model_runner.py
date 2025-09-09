import subprocess
from datetime import datetime, timedelta
from typing import Optional

from ramalama.common import generate_sha256
from ramalama.model_factory import CLASS_MODEL_TYPES


def generate_model_id(model: CLASS_MODEL_TYPES) -> str:
    return generate_sha256(f"{model.model_name}-{model.model_tag}-{model.model_organization}", with_sha_prefix=False)


class ManagedModel:

    def __init__(
        self,
        model: CLASS_MODEL_TYPES,
        run_cmd: list[str],
        port: int,
        expires_after: timedelta = timedelta(minutes=5),
    ):
        self.model = model
        self.id = generate_model_id(model)
        self.run_cmd: list[str] = run_cmd
        self.port: int = port

        self.expires_after = expires_after
        self.expiration_date: Optional[datetime] = None

        self.process: Optional[subprocess.Popen] = None

    def start(self):
        if self.process is not None:
            raise RuntimeError(f"Model {self.id} is already running.")
        self.update_expiration_date()
        self.process = subprocess.Popen(self.run_cmd)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def update_expiration_date(self):
        self.expiration_date = datetime.now() + self.expires_after


class ModelRunner:

    def __init__(self):
        self._models: dict[str, ManagedModel] = {}
        self._serve_path_model_id_map: dict[str, str] = {}

        self._port_range: tuple[int, int] = (8081, 9080)
        self._used_ports: set[int] = set()

    @property
    def managed_models(self) -> dict[str, ManagedModel]:
        return self._models

    @property
    def served_models(self) -> dict[str, ManagedModel]:
        return {path: self._models[id] for path, id in self._serve_path_model_id_map.items() if id in self._models}

    def next_available_port(self) -> int:
        for port in range(self._port_range[0], self._port_range[1] + 1):
            if port not in self._used_ports:
                self._used_ports.add(port)
                return port
        raise RuntimeError(f"No available ports in range {self._port_range[0]}-{self._port_range[1]}.")

    def add_model(self, model: ManagedModel):
        if model.id in self._models:
            raise RuntimeError(f"Model with ID {model.id} already exists.")

        self._models[model.id] = model

    def start_model(self, model_id: str, serve_path: str):
        if model_id not in self._models:
            raise RuntimeError(f"Model with ID {model_id} does not exist.")
        if serve_path in self._serve_path_model_id_map:
            raise RuntimeError(f"Model with ID {model_id} already served at {serve_path}")

        self._models[model_id].start()
        self._serve_path_model_id_map[serve_path] = model_id

    def stop_model(self, model_id: str):
        if model_id not in self._models:
            raise RuntimeError(f"Model with ID {model_id} does not exist.")

        id_to_path = {id: path for path, id in self._serve_path_model_id_map.items()}
        if model_id in id_to_path:
            path = id_to_path[model_id]
            del self._serve_path_model_id_map[path]

        m = self._models[model_id]
        m.stop()
        self._used_ports.discard(m.port)
        del self._models[model_id]

    def stop(self):
        for id in list(self._models.keys()):
            self.stop_model(id)
