import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, ClassVar, Literal, TypeVar, overload

from ramalama.common import get_accel

VersionerT = TypeVar("VersionerT")


@dataclass
class DeviceInfo:
    pass


@dataclass
class DeviceInfoV1(DeviceInfo):
    hostname: str
    operating_system: str
    cpu_info: str
    accel: str
    version: ClassVar[Literal["v1"]] = "v1"

    @classmethod
    @lru_cache(maxsize=1)
    def current_device_info(cls) -> "DeviceInfoV1":
        return cls(
            hostname=socket.gethostname(),
            operating_system=f"{platform.system()} {platform.release()}",
            cpu_info=platform.processor() or platform.machine(),
            accel=get_accel(),
        )


@dataclass
class TestConfiguration:
    pass


@dataclass
class TestConfigurationV1(TestConfiguration):
    """Container configuration metadata for a benchmark run."""

    container_image: str = ""
    container_runtime: str = ""
    inference_engine: str = ""
    version: Literal["v1"] = "v1"
    runtime_args: list[str] | None = None


@dataclass
class LlamaBenchResult:
    pass


@dataclass
class LlamaBenchResultV1(LlamaBenchResult):
    version: Literal["v1"] = "v1"
    build_commit: str | None = None
    build_number: int | None = None
    backends: str | None = None
    cpu_info: str | None = None
    gpu_info: str | None = None
    model_filename: str | None = None
    model_type: str | None = None
    model_size: int | None = None
    model_n_params: int | None = None
    n_batch: int | None = None
    n_ubatch: int | None = None
    n_threads: int | None = None
    cpu_mask: str | None = None
    cpu_strict: int | None = None
    poll: int | None = None
    type_k: str | None = None
    type_v: str | None = None
    n_gpu_layers: int | None = None
    n_cpu_moe: int | None = None
    split_mode: str | None = None
    main_gpu: int | None = None
    no_kv_offload: int | None = None
    flash_attn: int | None = None
    devices: str | None = None
    tensor_split: str | None = None
    tensor_buft_overrides: str | None = None
    use_mmap: int | None = None
    embeddings: int | None = None
    no_op_offload: int | None = None
    no_host: int | None = None
    n_prompt: int | None = None
    n_gen: int | None = None
    n_depth: int | None = None
    test_time: str | None = None
    avg_ns: int | None = None
    stddev_ns: int | None = None
    avg_ts: float | None = None
    stddev_ts: float | None = None
    samples_ns: str | None = None  # JSON array stored as string
    samples_ts: str | None = None  # JSON array stored as string

    @classmethod
    def from_payload(cls, payload: dict) -> "LlamaBenchResult":
        """Build a result from a llama-bench JSON/JSONL object."""
        return cls(**payload)


@dataclass
class BenchmarkRecord:
    pass


@dataclass
class BenchmarkRecordV1(BenchmarkRecord):
    configuration: TestConfigurationV1
    result: LlamaBenchResultV1
    version: Literal["v1"] = "v1"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    device: DeviceInfoV1 = field(default_factory=DeviceInfoV1.current_device_info)

    @classmethod
    def from_payload(cls, payload: dict) -> "BenchmarkRecordV1":
        payload = {**payload}

        if 'device' in payload:
            payload['device'] = DeviceInfoV1(**payload.pop("device"))

        configuration = TestConfigurationV1(**payload.pop('configuration', {}))
        result = LlamaBenchResultV1(**payload.pop('result', {}))

        return cls(configuration=configuration, result=result, **payload)


@overload
def get_device_info(payload: dict) -> DeviceInfoV1: ...


@overload
def get_device_info(payload: dict, version: Literal["v1"]) -> DeviceInfoV1: ...


def get_device_info(payload: dict, version: Any = None) -> DeviceInfo:
    if version is None:
        version = payload.get('version', "v1")

    if version == "v1":
        return DeviceInfoV1(**payload)

    raise NotImplementedError(f"No supported DeviceInfo schemas for version {version}")


@overload
def get_test_config(payload: dict) -> TestConfigurationV1: ...


@overload
def get_test_config(payload: dict, version: Literal["v1"]) -> TestConfigurationV1: ...


def get_test_config(payload: dict, version: Any = None) -> TestConfiguration:
    if version is None:
        version = payload.get('version', "v1")

    if version == "v1":
        return TestConfigurationV1(**payload)

    raise NotImplementedError(f"No supported TestConfiguration schemas for version {version}")


@overload
def get_llama_bench_result(payload: dict) -> LlamaBenchResultV1: ...


@overload
def get_llama_bench_result(payload: dict, version: Literal["v1"]) -> LlamaBenchResultV1: ...


def get_llama_bench_result(payload: dict, version: Any = None) -> LlamaBenchResult:
    if version is None:
        version = payload.get('version', "v1")

    if version == "v1":
        return LlamaBenchResultV1(**payload)

    raise NotImplementedError(f"No supported LlamaBench schemas for version {version}")


@overload
def get_benchmark_record(payload: dict) -> BenchmarkRecord: ...


@overload
def get_benchmark_record(payload: dict, version: Literal["v1"]) -> BenchmarkRecordV1: ...


def get_benchmark_record(payload: dict, version: Any = None) -> BenchmarkRecord:
    if version is None:
        version = payload.get('version', "v1")

    if version == "v1":
        return BenchmarkRecordV1.from_payload(payload)

    raise NotImplementedError(f"No supported benchmark schemas for version {version}")


def normalize_benchmark_record(benchmark: BenchmarkRecord) -> BenchmarkRecordV1:
    if isinstance(benchmark, BenchmarkRecordV1):
        return benchmark

    raise NotImplementedError(f"Received an unsupported benchmark record type {type(benchmark)}")
