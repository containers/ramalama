import json
from dataclasses import asdict
from functools import cached_property
from pathlib import Path

from ramalama.benchmarks.errors import MissingStorageFolderError
from ramalama.benchmarks.schemas import BenchmarkRecord, DeviceInfoV1, get_benchmark_record
from ramalama.benchmarks.utilities import parse_jsonl

SCHEMA_VERSION = 1
BENCHMARKS_FILENAME = "benchmarks.jsonl"


class BenchmarksManager:
    def __init__(self, storage_folder: str | Path | None):
        if storage_folder is None:
            raise MissingStorageFolderError

        self.storage_folder = Path(storage_folder)
        self.storage_file = self.storage_folder / BENCHMARKS_FILENAME
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)

    @cached_property
    def device_info(self) -> DeviceInfoV1:
        return DeviceInfoV1.current_device_info()

    def save(self, results: list[BenchmarkRecord] | BenchmarkRecord):
        if not isinstance(results, list):
            results = [results]

        if len(results) == 0:
            return

        with self.storage_file.open("a", encoding="utf-8") as handle:
            for record in results:
                handle.write(json.dumps(asdict(record), ensure_ascii=True))
                handle.write("\n")

    def list(self) -> list[BenchmarkRecord]:
        """List benchmark results from JSONL storage."""
        if not self.storage_file.exists():
            return []
        content = self.storage_file.read_text(encoding="utf-8")
        return [get_benchmark_record(result) for result in parse_jsonl(content)]
