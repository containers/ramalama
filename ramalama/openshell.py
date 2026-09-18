import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from ramalama.engine import Engine


@dataclass
class Route:
    name: str
    endpoint: str
    model: str
    protocols: list[str]
    api_key: str


@dataclass
class OpenShellInferenceConfig:
    routes: list[Route]

    def to_dict(self) -> dict:
        return {"routes": [route.__dict__ for route in self.routes]}

    def __str__(self) -> str:
        return yaml.safe_dump(self.to_dict(), indent=2, sort_keys=True)


def build_openshell_inference_config(url: str, model: str, api_key: str):
    return OpenShellInferenceConfig(
        [
            Route(
                name="inference.local",
                endpoint=f"{url}/v1",
                model=model,
                protocols=[
                    "openai_chat_completions",
                    "openai_completions",
                    "openai_responses",
                    "openai_embeddings",
                    "model_discovery",
                ],
                api_key=api_key,
            )
        ]
    )


@dataclass
class Endpoint:
    host: str
    port: str
    protocol: str
    enforcement: str
    access: str


@dataclass
class NetworkPolicy:
    name: str
    endpoints: list[Endpoint]
    binaries: list[str]

    def to_dict(self):
        return {
            "name": self.name,
            "endpoints": [endpoint.__dict__ for endpoint in self.endpoints],
            "binaries": self.binaries,
        }


@dataclass
class FileSystemPolicy:
    include_workdir: bool
    read_only: list[str]
    read_write: list[str]


@dataclass
class LandLock:
    compatibility: str


@dataclass
class AgentProcess:
    run_as_user: str
    run_as_group: str


@dataclass
class OpenShellPolicyConfig:
    version: int
    filesystem_policy: FileSystemPolicy
    landlock: LandLock
    process: AgentProcess
    network_policies: dict[str, NetworkPolicy]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "filesystem_policy": self.filesystem_policy.__dict__,
            "landlock": self.landlock.__dict__,
            "process": self.process.__dict__,
            "network_policies": {key: policy.to_dict() for key, policy in self.network_policies.items()},
        }

    def __str__(self) -> str:
        return yaml.safe_dump(self.to_dict(), indent=2, sort_keys=True)


def default_openshell_goose_policy_config():
    return OpenShellPolicyConfig(
        version=1,
        filesystem_policy=FileSystemPolicy(
            include_workdir=True,
            read_only=["/usr", "/lib", "/lib64", "/bin", "/sbin", "/proc", "/etc", "/dev/urandom", "/var/log"],
            read_write=["/sandbox", "/tmp", "/dev/null", "/dev/shm", "/home/goose", "/work"],
        ),
        landlock=LandLock(compatibility="best_effort"),
        process=AgentProcess(run_as_user="goose", run_as_group="goose"),
        network_policies={},
    )


def create_temp_openshell_inference_config(inference_url: str, model_name: str, api_key: str) -> Path:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        conf = build_openshell_inference_config(inference_url, model_name, api_key)
        f.write(f"{conf}".encode("utf-8"))
        return Path(f.name)


def create_temp_openshell_policy_config(policy: OpenShellPolicyConfig) -> Path:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(f"{policy}".encode("utf-8"))
        return Path(f.name)


def add_capabilities(engine: Engine) -> None:
    engine.add_args(
        "--security-opt=no-new-privileges",
        "--security-opt=seccomp=unconfined",
        "--cap-add=sys_admin",
        "--cap-add=net_admin",
        "--cap-add=sys_ptrace",
        "--cap-add=syslog",
        "--cap-add=dac_read_search",
        "--cap-add=setpcap",
        "--cap-add=setuid",
        "--cap-add=setgid",
    )


def add_openshell_args(engine: Engine, policy: Path, inference: Path, openshell_image: str, entry_point: str) -> None:
    engine.add_args(
        "-v",
        f"{policy}:/etc/openshell/policy.yaml:ro",
        "-v",
        f"{inference}:/etc/openshell/inference-routes.yaml:ro",
        openshell_image,
        "--interactive",
        "--log-level",
        "error",
        "--policy-rules",
        "/etc/openshell/opa.rego",
        "--policy-data",
        "/etc/openshell/policy.yaml",
        "--inference-routes",
        "/etc/openshell/inference-routes.yaml",
        entry_point,
    )
