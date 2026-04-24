from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, ClassVar, Literal, Optional, TypeVar, overload

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
    runtime_args: Optional[list[str]] = None


@dataclass
class LlamaBenchResult:
    pass


@dataclass
class LlamaBenchResultV1(LlamaBenchResult):
    version: Literal["v1"] = "v1"
    build_commit: Optional[str] = None
    build_number: Optional[int] = None
    backends: Optional[str] = None
    cpu_info: Optional[str] = None
    gpu_info: Optional[str] = None
    model_filename: Optional[str] = None
    model_type: Optional[str] = None
    model_size: Optional[int] = None
    model_n_params: Optional[int] = None
    n_batch: Optional[int] = None
    n_ubatch: Optional[int] = None
    n_threads: Optional[int] = None
    cpu_mask: Optional[str] = None
    cpu_strict: Optional[int] = None
    poll: Optional[int] = None
    type_k: Optional[str] = None
    type_v: Optional[str] = None
    n_gpu_layers: Optional[int] = None
    n_cpu_moe: Optional[int] = None
    split_mode: Optional[str] = None
    main_gpu: Optional[int] = None
    no_kv_offload: Optional[int] = None
    flash_attn: Optional[int] = None
    devices: Optional[str] = None
    tensor_split: Optional[str] = None
    tensor_buft_overrides: Optional[str] = None
    use_mmap: Optional[int] = None
    embeddings: Optional[int] = None
    no_op_offload: Optional[int] = None
    no_host: Optional[int] = None
    use_direct_io: Optional[int] = None
    fit_target: Optional[int] = None
    n_prompt: Optional[int] = None
    n_gen: Optional[int] = None
    n_depth: Optional[int] = None
    test_time: Optional[str] = None
    avg_ns: Optional[int] = None
    stddev_ns: Optional[int] = None
    avg_ts: Optional[float] = None
    stddev_ts: Optional[float] = None
    samples_ns: Optional[str] = None  # JSON array stored as string
    samples_ts: Optional[str] = None  # JSON array stored as string

    @classmethod
    def from_payload(cls, payload: dict) -> "LlamaBenchResultV1":
        """Build a result from a llama-bench JSON/JSONL object."""
        return cls(**{f.name: payload[f.name] for f in fields(cls) if f.name in payload})


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
        result = LlamaBenchResultV1.from_payload(payload.pop('result', {}))

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
        return LlamaBenchResultV1.from_payload(payload)

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
