import sqlite3

from ramalama.benchmarks import llama_bench, manager


def _patch_config(monkeypatch, tmp_path):
    # Avoid external engine calls and keep paths isolated per test.
    monkeypatch.setattr(manager.CONFIG, "engine", None)
    monkeypatch.setattr(manager.CONFIG, "runtime", "llama.cpp")
    monkeypatch.setattr(manager.CONFIG, "store", str(tmp_path / "store"))
    monkeypatch.setattr(manager.CONFIG, "container", False)
    monkeypatch.setattr(manager, "get_accel", lambda: "none")


def test_migrate_creates_schema(tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    db_path = tmp_path / "bench.sqlite"

    manager.migrate(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {row[0] for row in cur.fetchall()}
    assert {"meta", "user_device", "container_configuration", "llama_bench"} <= table_names

    cur.execute("SELECT value FROM meta WHERE key='schema_version'")
    assert cur.fetchone()[0] == "1"
    con.close()


def test_update_user_device_idempotent(tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    db_path = tmp_path / "bench.sqlite"
    manager.migrate(db_path)

    first_id = manager.update_user_device(db_path)
    second_id = manager.update_user_device(db_path)

    assert first_id == second_id

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM user_device")
    assert cur.fetchone()[0] == 1
    con.close()


def test_save_llama_bench_result_inserts_all(tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    db_path = tmp_path / "bench.sqlite"
    db = manager.DBManager(db_path)

    cfg = llama_bench.TestConfiguration(
        container_image="quay.io/ramalama/ramalama:latest",
        container_runtime="docker",
        inference_engine="llama.cpp",
        runtime_args={"threads": 2},
    )
    res = llama_bench.LlamaBenchResult(
        build_commit="abc123",
        build_number=1,
        cpu_info="cpu",
        gpu_info="gpu",
        model_filename="model.gguf",
        n_threads=2,
        n_prompt=8,
        n_gen=16,
        avg_ts=1.5,
        stddev_ts=0.1,
    )

    inserted = db.save_llama_bench_result(cfg, res)
    assert inserted in (None, 1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM user_device")
    assert cur.fetchone()[0] == 1

    cur.execute(
        "SELECT id, user_device_id, container_image, container_runtime, inference_engine, runtime_args "
        "FROM container_configuration"
    )
    container_row = cur.fetchone()
    assert container_row is not None
    container_id = container_row[0]
    assert container_row[2:] == (
        "quay.io/ramalama/ramalama:latest",
        "docker",
        "llama.cpp",
        '{"threads": 2}',
    )

    cur.execute(
        "SELECT test_configuration_id, build_commit, model_filename, n_threads, n_prompt, n_gen, avg_ts, stddev_ts "
        "FROM llama_bench"
    )
    bench_row = cur.fetchone()
    assert bench_row is not None
    assert bench_row[0] == container_id
    assert bench_row[1:] == ("abc123", "model.gguf", 2, 8, 16, 1.5, 0.1)
    con.close()
