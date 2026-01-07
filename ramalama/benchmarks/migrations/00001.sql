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

CREATE UNIQUE INDEX IF NOT EXISTS container_configuration_uniq
ON container_configuration(
  user_device_id,
  container_image,
  container_runtime,
  inference_engine,
  COALESCE(runtime_args, '')
);

CREATE TABLE IF NOT EXISTS llama_bench (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_configuration_id INTEGER NOT NULL REFERENCES container_configuration(id) ON DELETE CASCADE,
  build_commit TEXT,
  build_number INTEGER,
  backends TEXT,
  cpu_info TEXT,
  gpu_info TEXT,
  model_filename TEXT,
  model_type TEXT,
  model_size INTEGER,
  model_n_params INTEGER,
  n_batch INTEGER,
  n_ubatch INTEGER,
  n_threads INTEGER,
  cpu_mask TEXT,
  cpu_strict INTEGER,
  poll INTEGER,
  type_k TEXT,
  type_v TEXT,
  n_gpu_layers INTEGER,
  n_cpu_moe INTEGER,
  split_mode TEXT,
  main_gpu INTEGER,
  no_kv_offload INTEGER,
  flash_attn INTEGER,
  devices TEXT,
  tensor_split TEXT,
  tensor_buft_overrides TEXT,
  use_mmap INTEGER,
  embeddings INTEGER,
  no_op_offload INTEGER,
  no_host INTEGER,
  n_prompt INTEGER,
  n_gen INTEGER,
  n_depth INTEGER,
  test_time TEXT,
  avg_ns INTEGER,
  stddev_ns INTEGER,
  avg_ts REAL,
  stddev_ts REAL,
  samples_ns TEXT,
  samples_ts TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
COMMIT;
