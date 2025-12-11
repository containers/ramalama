import json
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable
from typing_extensions import runtime


# Columns match the initial migration schema for the llama_bench table.
TABLE_COLUMNS: list[str] = [
    "build_commit",
    "build_number",
    "cuda",
    "opencl",
    "metal",
    "gpu_blas",
    "blas",
    "cpu_info",
    "gpu_info",
    "model_filename",
    "model_type",
    "model_size",
    "model_n_params",
    "n_batch",
    "n_threads",
    "f16_kv",
    "n_gpu_layers",
    "main_gpu",
    "mul_mat_q",
    "tensor_split",
    "n_prompt",
    "n_gen",
    "test_time",
    "avg_ns",
    "stddev_ns",
    "avg_ts",
    "stddev_ts",
]

INT_FIELDS = {
    "build_number",
    "cuda",
    "opencl",
    "metal",
    "gpu_blas",
    "blas",
    "model_size",
    "model_n_params",
    "n_batch",
    "n_threads",
    "f16_kv",
    "n_gpu_layers",
    "main_gpu",
    "mul_mat_q",
    "n_prompt",
    "n_gen",
    "avg_ns",
    "stddev_ns",
}

FLOAT_FIELDS = {
    "avg_ts",
    "stddev_ts",
}


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class TestConfiguration:
    container_image: str
    container_runtime: str
    inference_engine: str
    runtime_args: str | dict | list | None

    def as_db_tuple(self, user_device_id: int):
        if self.runtime_args is None:
            runtime_args = ""
        elif isinstance(self.runtime_args, str):
            runtime_args = self.runtime_args
        else:
            runtime_args = json.dumps(self.runtime_args)

        return (
            user_device_id,
            self.container_image,
            self.container_runtime,
            self.inference_engine,
            runtime_args,
        )


@dataclass
class LlamaBenchResult:
    build_commit: str | None = None
    build_number: int | None = None
    cuda: int | None = None
    opencl: int | None = None
    metal: int | None = None
    gpu_blas: int | None = None
    blas: int | None = None
    cpu_info: str | None = None
    gpu_info: str | None = None
    model_filename: str | None = None
    model_type: str | None = None
    model_size: int | None = None
    model_n_params: int | None = None
    n_batch: int | None = None
    n_threads: int | None = None
    f16_kv: int | None = None
    n_gpu_layers: int | None = None
    main_gpu: int | None = None
    mul_mat_q: int | None = None
    tensor_split: str | None = None
    n_prompt: int | None = None
    n_gen: int | None = None
    test_time: str | None = None
    avg_ns: int | None = None
    stddev_ns: int | None = None
    avg_ts: float | None = None
    stddev_ts: float | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "LlamaBenchResult":
        """Build a result from a llama-bench JSON/JSONL object."""
        kwargs: dict[str, Any] = {}
        for col in TABLE_COLUMNS:
            raw_val = payload.get(col)
            if col in FLOAT_FIELDS:
                kwargs[col] = _as_float(raw_val)
            elif col in INT_FIELDS:
                kwargs[col] = _as_int(raw_val)
            else:
                kwargs[col] = None if raw_val is None else str(raw_val)
        return cls(**kwargs)

    def as_db_tuple(self) -> tuple[Any, ...]:
        """Return values ordered to match TABLE_COLUMNS for parameterized inserts."""
        return tuple(getattr(self, col) for col in TABLE_COLUMNS)

    def as_dict(self) -> dict[str, Any]:
        return {col: getattr(self, col) for col in TABLE_COLUMNS}


def parse_jsonl(stream: str) -> list[LlamaBenchResult]:
    """Parse newline-delimited JSON into a list of LlamaBenchResult objects."""
    results: list[LlamaBenchResult] = []
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        results.append(LlamaBenchResult.from_payload(payload))
    return results


def parse_json(blob: str) -> list[LlamaBenchResult]:
    """Parse a JSON array or single object into LlamaBenchResult objects."""
    payload = json.loads(blob)
    if isinstance(payload, list):
        return [LlamaBenchResult.from_payload(item) for item in payload]
    return [LlamaBenchResult.from_payload(payload)]


def iter_db_rows(results: Iterable[LlamaBenchResult]) -> Iterable[tuple[Any, ...]]:
    """Yield database-ready tuples from an iterable of results."""
    for result in results:
        yield result.as_db_tuple()
