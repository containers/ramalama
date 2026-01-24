import json

import pytest

from ramalama.benchmarks import manager, schemas


def _make_config(engine: str) -> schemas.TestConfigurationV1:
    return schemas.TestConfigurationV1(
        container_image="quay.io/ramalama/ramalama:latest",
        container_runtime="docker",
        inference_engine=engine,
        runtime_args={"threads": 2},
    )


def _make_result(model_name: str, avg_ts: float) -> schemas.LlamaBenchResultV1:
    return schemas.LlamaBenchResultV1(
        build_commit="abc123",
        build_number=1,
        cpu_info="cpu",
        gpu_info="gpu",
        model_filename=model_name,
        n_threads=2,
        n_prompt=8,
        n_gen=16,
        avg_ts=avg_ts,
        stddev_ts=0.1,
    )


def _make_device() -> schemas.DeviceInfoV1:
    return schemas.DeviceInfoV1(
        hostname="host",
        operating_system="TestOS 1.0",
        cpu_info="cpu",
        accel="none",
    )


def test_save_benchmark_record_writes_jsonl(tmp_path):
    db = manager.BenchmarksManager(tmp_path)
    cfg = _make_config("llama.cpp")
    res = _make_result("model.gguf", 1.5)
    device = _make_device()
    record = schemas.BenchmarkRecordV1(
        configuration=cfg,
        result=res,
        created_at="2024-01-01 00:00:00",
        device=device,
    )

    db.save(record)

    assert db.storage_file.exists()
    payload = json.loads(db.storage_file.read_text().strip())

    assert payload["version"] == "v1"
    assert payload["created_at"] == "2024-01-01 00:00:00"
    assert payload["configuration"]["inference_engine"] == "llama.cpp"
    assert payload["result"]["model_filename"] == "model.gguf"
    assert payload["device"]["hostname"] == "host"


def test_list_empty_returns_empty_list(tmp_path):
    db = manager.BenchmarksManager(tmp_path)

    records = db.list()

    assert records == []


def test_manager_missing_storage_folder_raises():
    with pytest.raises(manager.MissingStorageFolderError):
        manager.BenchmarksManager(None)


def test_list_returns_saved_records_in_order(tmp_path):
    db = manager.BenchmarksManager(tmp_path)
    device = _make_device()

    cfg_a = _make_config("engine-a")
    cfg_b = _make_config("engine-b")

    res_a = _make_result("model-a.gguf", 1.0)
    res_b = _make_result("model-b.gguf", 2.0)

    record_a = schemas.BenchmarkRecordV1(
        configuration=cfg_a,
        result=res_a,
        created_at="2024-01-01 00:00:00",
        device=device,
    )
    record_b = schemas.BenchmarkRecordV1(
        configuration=cfg_b,
        result=res_b,
        created_at="2024-01-02 00:00:00",
        device=device,
    )

    db.save([record_a, record_b])

    stored = db.list()
    assert len(stored) == 2
    assert stored[0].configuration.inference_engine == "engine-a"
    assert stored[1].configuration.inference_engine == "engine-b"

    assert stored[0].result.avg_ts == 1.0
    assert stored[1].result.avg_ts == 2.0
