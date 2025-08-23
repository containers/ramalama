import subprocess
from typing import Optional

from ramalama.common import generate_sha256
from ramalama.model_factory import CLASS_MODEL_TYPES


class ManagedModel:

    def __init__(self, id: str, model: CLASS_MODEL_TYPES, run_cmd: list[str], port: int):
        self.id = id
        self.model = model
        self.run_cmd: list[str] = run_cmd
        self.port: str = port
        self.process: Optional[subprocess.Popen] = None

    def start(self):
        if self.process is not None:
            raise RuntimeError(f"Model {self.id} is already running.")
        self.process = subprocess.Popen(self.run_cmd)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None


class ModelRunner:

    def __init__(self):
        self._models: dict[str, ManagedModel] = {}

        self._port_range: tuple[int, int] = (8081, 9080)
        self._used_ports: set[int] = set()

    @property
    def managed_models(self) -> dict[str, ManagedModel]:
        return self._models

    def next_available_port(self) -> int:
        for port in range(self._port_range[0], self._port_range[1] + 1):
            if port not in self._used_ports:
                self._used_ports.add(port)
                return port
        raise RuntimeError(f"No available ports in range {self._port_range[0]}-{self._port_range[1]}.")

    @staticmethod
    def generate_model_id(model_name: str, model_tag: str, model_organization: str) -> str:
        return generate_sha256(f"{model_name}-{model_tag}-{model_organization}")

    def add_model(self, model: ManagedModel):
        if model.id in self._models:
            raise ValueError(f"Model with ID {id} already exists.")

        self._models[model.id] = model

    def start_model(self, model_id: str):
        if model_id not in self._models:
            raise ValueError(f"Model with ID {model_id} does not exist.")
        self._models[model_id].start()

    def stop_model(self, model_id: str):
        if model_id not in self._models:
            raise ValueError(f"Model with ID {model_id} does not exist.")
        self._models[model_id].stop()
        self._used_ports.discard(self._models[model_id].port)
        del self._models[model_id]

    def stop(self):
        for id in self._models.keys():
            self.stop_model(id)
