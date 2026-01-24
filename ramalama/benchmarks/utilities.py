import json

from ramalama.benchmarks.schemas import (
    BenchmarkRecord,
    BenchmarkRecordV1,
    normalize_benchmark_record,
)


def parse_jsonl(content: str) -> list[dict]:
    """Parse newline-delimited JSON benchmark results."""
    results = []
    for line in content.strip().split("\n"):
        if not line.strip():
            continue
        results.append(json.loads(line))
    return results


def parse_json(content: str) -> list[dict]:
    """Parse JSON array or single object benchmark results."""
    data = json.loads(content)
    if not isinstance(data, list):
        data = [data]
    return data


def print_bench_results(records: list[BenchmarkRecord]):
    """Format benchmark results as a table for display."""
    if not records:
        return
    normalized_records: list[BenchmarkRecordV1] = [normalize_benchmark_record(result) for result in records]

    rows: list[dict[str, object | None]] = []
    for i, item in enumerate(normalized_records):
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
                "id": i,
                "model": model,
                "params": params,
                "backend": backend,
                "ngl": ngl,
                "threads": threads,
                "test": test,
                "t/s": t_s,
                "engine": item.configuration.container_runtime,
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
