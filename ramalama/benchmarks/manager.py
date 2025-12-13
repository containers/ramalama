import logging
import platform
import socket
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, Cursor
from types import SimpleNamespace

from ramalama import engine
from ramalama.benchmarks import llama_bench
from ramalama.benchmarks.errors import MissingDBPathError
from ramalama.common import accel_image, get_accel
from ramalama.config import CONFIG, get_inference_schema_files, get_inference_spec_files, load_file_config
from ramalama.log_levels import LogLevel
from ramalama.rag import rag_image
from ramalama.version import version

logger = logging.getLogger("ramalama.benchmarks")
logger.setLevel(CONFIG.log_level or LogLevel.WARNING)


@contextmanager
def get_conn(db_path: Path | str) -> Generator[Connection, None, None]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;
    PRAGMA foreign_keys = ON;
    """
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


LATEST_SCHEMA_VERSION = 1


def initialize_db(cur: Cursor):
    sql_path = Path(__file__).with_name("migrations") / "00001.sql"
    cur.executescript(sql_path.read_text())


def run_next_migration(cursor: Cursor, from_version: int):
    if from_version == LATEST_SCHEMA_VERSION:
        return

    if from_version == 0:
        initialize_db(cursor)
    else:
        raise RuntimeError(f"No migration path {from_version} -> {from_version + 1}")


class DBMigrationManager:
    def __init__(self, cur: Cursor):
        self.cursor = cur

    def has_schema(self) -> bool:
        self.cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meta'
         """
        )
        return self.cursor.fetchone() is not None

    def get_schema_version(self) -> int:
        if not self.has_schema():
            return 0

        self.cursor.execute("SELECT value FROM meta WHERE key = 'schema_version'")
        row = self.cursor.fetchone()
        if row is None:
            return 0

        return int(row[0])

    def update_schema_version(self, version: int) -> int:
        self.cursor.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(version),),
        )
        return version

    def run_migrations(self):
        schema_version = self.get_schema_version()

        while schema_version < LATEST_SCHEMA_VERSION:
            to_version = schema_version + 1

            logger.info("Running database migrations from %s to %s", schema_version, to_version)
            run_next_migration(self.cursor, schema_version)
            self.update_schema_version(to_version)

            schema_version = to_version


def migrate(db_path: str | Path):
    with get_conn(db_path) as connection:
        db = DBMigrationManager(connection.cursor())
        db.run_migrations()


def _current_device_info() -> tuple[str, str, str, str, str]:
    """Collect current device info reusing the same sources as `ramalama info`."""
    args = SimpleNamespace(
        engine=CONFIG.engine,
        runtime=CONFIG.runtime,
        store=CONFIG.store,
        container=CONFIG.container,
        quiet=True,
    )

    info = {
        "Accelerator": get_accel(),
        "Config": load_file_config(),
        "Engine": {"Name": args.engine},
        "Image": accel_image(CONFIG),
        "Inference": {
            "Default": args.runtime,
            "Engines": {spec: str(path) for spec, path in get_inference_spec_files().items()},
            "Schema": {schema: str(path) for schema, path in get_inference_schema_files().items()},
        },
        "RagImage": rag_image(CONFIG),
        "Selinux": CONFIG.selinux,
        "Shortnames": {},
        "Store": args.store,
        "UseContainer": args.container,
        "Version": version(),
    }

    engine_info = None
    if args.engine:
        try:
            engine_info = engine.info(args)
            info["Engine"]["Info"] = engine_info
        except Exception as exc:  # type: ignore[broad-except]
            logger.debug("Failed to collect engine info: %s", exc)

    hostname = socket.gethostname()
    operating_system = f"{platform.system()} {platform.release()}"
    cpu_info = platform.processor() or platform.machine()
    gpu_info = ""
    accel = info["Accelerator"] or "cpu"

    if isinstance(engine_info, dict):
        hostname = engine_info.get("Name", hostname) or hostname
        operating_system = engine_info.get("OperatingSystem", operating_system) or operating_system
        cpu_info = engine_info.get("Architecture", cpu_info) or cpu_info
        devices = engine_info.get("DiscoveredDevices") or []
        if isinstance(devices, list) and devices:
            gpu_info = ", ".join(str(d.get("ID", d)) for d in devices if d)

    return hostname, operating_system, cpu_info, gpu_info, accel


def update_user_device(db_path: str | Path) -> int:
    """Upsert the current user_device row and return its id."""
    hostname, operating_system, cpu_info, gpu_info, accel = _current_device_info()

    with get_conn(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id FROM user_device
            WHERE hostname = ? AND operating_system = ? AND cpu_info = ? AND gpu_info = ? AND accel = ?
            ORDER BY id DESC LIMIT 1
            """,
            (hostname, operating_system, cpu_info, gpu_info, accel),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0])

        cursor.execute(
            """
            INSERT INTO user_device (hostname, operating_system, cpu_info, gpu_info, accel)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hostname, operating_system, cpu_info, gpu_info, accel),
        )

        if (current_device_info_id := cursor.lastrowid) is None:
            raise Exception("should never reach here")

        return int(current_device_info_id)


class DBManager:
    def __init__(self, db_path: str | Path | None):
        if db_path is None:
            raise MissingDBPathError

        self.db_path = db_path
        migrate(self.db_path)
        self.user_device_id = update_user_device(self.db_path)

    def save_llama_bench_result(
        self, configuration: llama_bench.TestConfiguration, result: llama_bench.LlamaBenchResult
    ):
        """Insert a single llama-bench result row. Returns rows inserted (1 or 0)."""

        configuration_id = self.save_container_configuration(configuration)

        columns = ["test_configuration_id"] + llama_bench.TABLE_COLUMNS
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO llama_bench ({', '.join(columns)}) VALUES ({placeholders})"
        values = (configuration_id, *result.as_db_tuple())

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(insert_sql, values)

    def save_container_configuration(self, configuration: llama_bench.TestConfiguration) -> int:
        """Insert a container_configuration row and return its id."""
        values = configuration.as_db_tuple(self.user_device_id)

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO container_configuration (
                    user_device_id, container_image, container_runtime, inference_engine, runtime_args
                ) VALUES (?, ?, ?, ?, ?)
                """,
                values,
            )
            rowid = cursor.lastrowid

        if rowid is None:
            raise Exception("Should never reach here")
        return int(rowid)

    def list_benchmarks(self, limit: int | None = None, offset: int = 0):
        """List benchmark results with device and configuration info."""
        query = """
            SELECT
                lb.id,
                lb.model_filename,
                lb.model_size,
                lb.model_n_params,
                lb.n_prompt,
                lb.n_gen,
                lb.test_time,
                lb.avg_ts as tokens_per_sec,
                lb.stddev_ts as stddev_tokens_per_sec,
                cc.inference_engine,
                cc.container_runtime,
                cc.runtime_args,
                ud.hostname,
                ud.cpu_info,
                ud.gpu_info,
                lb.backends as accel,
                datetime(lb.created_at) as created_at
            FROM llama_bench lb
            JOIN container_configuration cc ON lb.test_configuration_id = cc.id
            JOIN user_device ud ON cc.user_device_id = ud.id
            ORDER BY lb.created_at DESC, lb.id DESC
        """

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            return cursor.fetchall()
