BEGIN;
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

INSERT INTO meta (key, value) VALUES ('schema_version', '1');

CREATE TABLE IF NOT EXISTS user_device (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hostname TEXT, 
  operating_system TEXT,
  cpu_info TEXT,
  gpu_info TEXT,
  accel TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS container_configuration (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_device_id INTEGER NOT NULL REFERENCES user_device(id) ON DELETE CASCADE,
  container_image TEXT,
  container_runtime TEXT,
  inference_engine TEXT,
  runtime_args TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llama_bench (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_configuration_id INTEGER NOT NULL REFERENCES container_configuration(id) ON DELETE CASCADE,
  build_commit TEXT,
  build_number INTEGER,
  cuda INTEGER,
  opencl INTEGER,
  metal INTEGER,
  gpu_blas INTEGER,
  blas INTEGER,
  cpu_info TEXT,
  gpu_info TEXT,
  model_filename TEXT,
  model_type TEXT,
  model_size INTEGER,
  model_n_params INTEGER,
  n_batch INTEGER,
  n_threads INTEGER,
  f16_kv INTEGER,
  n_gpu_layers INTEGER,
  main_gpu INTEGER,
  mul_mat_q INTEGER,
  tensor_split TEXT,
  n_prompt INTEGER,
  n_gen INTEGER,
  test_time TEXT,
  avg_ns INTEGER,
  stddev_ns INTEGER,
  avg_ts REAL,
  stddev_ts REAL,
  created_at TEXT DEFAULT (datetime('now'))
);
COMMIT;
