"""
Data models and parsing for llama-bench JSON output.
"""

import json
from dataclasses import dataclass
from typing import Any

# Column order for database inserts (matches llama_bench table schema)
TABLE_COLUMNS = [
    "build_commit",
    "build_number",
    "backends",
    "cpu_info",
    "gpu_info",
    "model_filename",
    "model_type",
    "model_size",
    "model_n_params",
    "n_batch",
    "n_ubatch",
    "n_threads",
    "cpu_mask",
    "cpu_strict",
    "poll",
    "type_k",
    "type_v",
    "n_gpu_layers",
    "n_cpu_moe",
    "split_mode",
    "main_gpu",
    "no_kv_offload",
    "flash_attn",
    "devices",
    "tensor_split",
    "tensor_buft_overrides",
    "use_mmap",
    "embeddings",
    "no_op_offload",
    "no_host",
    "n_prompt",
    "n_gen",
    "n_depth",
    "test_time",
    "avg_ns",
    "stddev_ns",
    "avg_ts",
    "stddev_ts",
    "samples_ns",
    "samples_ts",
]

INT_FIELDS = {
    "build_number",
    "model_size",
    "model_n_params",
    "n_batch",
    "n_ubatch",
    "n_threads",
    "cpu_strict",
    "poll",
    "n_gpu_layers",
    "n_cpu_moe",
    "main_gpu",
    "no_kv_offload",
    "flash_attn",
    "use_mmap",
    "embeddings",
    "no_op_offload",
    "no_host",
    "n_prompt",
    "n_gen",
    "n_depth",
    "avg_ns",
    "stddev_ns",
}

FLOAT_FIELDS = {
    "avg_ts",
    "stddev_ts",
}


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@dataclass
class TestConfiguration:
    """Container configuration metadata for a benchmark run."""

    container_image: str = ""
    container_runtime: str = ""
    inference_engine: str = ""
    runtime_args: dict[str, Any] | None = None

    def as_db_tuple(self, user_device_id: int) -> tuple:
        """Return values for database insert."""
        return (
            user_device_id,
            self.container_image,
            self.container_runtime,
            self.inference_engine,
            json.dumps(self.runtime_args) if self.runtime_args else None,
        )

    @classmethod
    def from_args(cls, args) -> "TestConfiguration":
        container_image = getattr(args, "image", "") if args.container else ""
        container_runtime = getattr(args, "engine", "") if args.container else ""

        runtime_args = {
            "threads": getattr(args, "threads", None),
            "ctx_size": getattr(args, "ctx_size", None),
            "gpu_layers": getattr(args, "gpu_layers", None),
            "batch_size": getattr(args, "batch_size", None),
        }
        runtime_args = {k: v for k, v in runtime_args.items() if v is not None}

        return TestConfiguration(
            container_image=container_image,
            container_runtime=container_runtime,
            inference_engine=getattr(args, "runtime", ""),
            runtime_args=runtime_args if runtime_args else None,
        )


@dataclass
class LlamaBenchResult:
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
    def from_payload(cls, payload: dict[str, Any]) -> "LlamaBenchResult":
        """Build a result from a llama-bench JSON/JSONL object."""
        kwargs: dict[str, Any] = {}
        for col in TABLE_COLUMNS:
            raw_val = payload.get(col)

            # Convert arrays to JSON strings
            if col in ("samples_ns", "samples_ts"):
                if isinstance(raw_val, list):
                    kwargs[col] = json.dumps(raw_val)
                else:
                    kwargs[col] = raw_val
            elif col in FLOAT_FIELDS:
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


def parse_jsonl(content: str) -> list[LlamaBenchResult]:
    """Parse newline-delimited JSON benchmark results."""
    results = []
    for line in content.strip().split("\n"):
        if not line.strip():
            continue
        result = json.loads(line)
        results.append(LlamaBenchResult.from_payload(result))
    return results


def parse_json(content: str) -> list[LlamaBenchResult]:
    """Parse JSON array or single object benchmark results."""
    data = json.loads(content)
    if not isinstance(data, list):
        data = [data]
    return [LlamaBenchResult.from_payload(result) for result in data]


def iter_db_rows(results: list[LlamaBenchResult], config_id: int):
    """Yield (config_id, *result) tuples for database insertion."""
    for result in results:
        yield (config_id, *result.as_db_tuple())


@dataclass
class LlamaBenchResultItem:
    result: LlamaBenchResult
    id: int | None = None
    engine: str | None = None
    created_at: str | None = None


@dataclass
class LlamaBenchResultCollection:
    results: list[LlamaBenchResultItem]

    @classmethod
    def from_list(cls, results: list[LlamaBenchResult]):
        return cls(results=[LlamaBenchResultItem(result=result) for result in results])

    def __iter__(self):
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)


def print_bench_results(res: LlamaBenchResultCollection | list[LlamaBenchResult]):
    """Format benchmark results as a table for display."""
    if not res:
        return

    results = res if isinstance(res, LlamaBenchResultCollection) else LlamaBenchResultCollection.from_list(res)

    rows: list[dict[str, object | None]] = []
    for item in results.results:
        result = item.result
        model = result.model_filename or ""
        params = f"{result.model_n_params / 1e9:.2f} B" if result.model_n_params else "-"
        backend = result.gpu_info or result.cpu_info or "CPU"
        ngl = str(result.n_gpu_layers) if result.n_gpu_layers else "-"
        threads = str(result.n_threads) if result.n_threads else "-"

        # Format test type
        if result.n_prompt and result.n_gen:
            test = f"pp{result.n_prompt}+tg{result.n_gen}"
        elif result.n_prompt:
            test = f"pp{result.n_prompt}"
        elif result.n_gen:
            test = f"tg{result.n_gen}"
        else:
            test = "-"

        # Format tokens/sec with stddev
        if result.avg_ts and result.stddev_ts:
            t_s = f"{result.avg_ts:.2f} ± {result.stddev_ts:.2f}"
        elif result.avg_ts:
            t_s = f"{result.avg_ts:.2f}"
        else:
            t_s = "-"

        rows.append(
            {
                "id": item.id,
                "model": model,
                "params": params,
                "backend": backend,
                "ngl": ngl,
                "threads": threads,
                "test": test,
                "t/s": t_s,
                "engine": item.engine,
                "date": item.created_at,
            }
        )

    optional_fields = ["id", "engine", "date"]
    for field in optional_fields:
        if all(not row.get(field) for row in rows):
            for row in rows:
                row.pop(field, None)

    column_order = ["id", "model", "params", "backend", "ngl", "threads", "test", "t/s", "engine", "date"]
    headers = [column for column in column_order if column in rows[0]]

    col_widths: dict[str, int] = {}
    for header in headers:
        max_len = len(header)
        for row in rows:
            value = row.get(header)
            text = "-" if value in (None, "") else str(value)
            max_len = max(max_len, len(text))
        col_widths[header] = max_len

    header_row = " | ".join(header.ljust(col_widths[header]) for header in headers)
    print(f"| {header_row} |")
    print(f"| {'-' * len(header_row)} |")

    for row in rows:
        cells = []
        for header in headers:
            value = row.get(header)
            text = "-" if value in (None, "") else str(value)
            cells.append(text.ljust(col_widths[header]))
        print(f"| {' | '.join(cells)} |")

    # Print build info if available
    if results.results and results.results[0].result.build_commit:
        build = results.results[0].result
        print(f"\nbuild: {build.build_commit} ({build.build_number or 1})")
