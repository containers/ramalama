import logging
import platform
import socket
import sqlite3
from collections.abc import Collection, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection, Cursor

from ramalama.benchmarks.errors import MissingDBPathError
from ramalama.benchmarks.llama_bench import (
    TABLE_COLUMNS,
    LlamaBenchResult,
    LlamaBenchResultCollection,
    LlamaBenchResultItem,
    TestConfiguration,
)
from ramalama.common import get_accel
from ramalama.config import CONFIG
from ramalama.log_levels import LogLevel

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


@dataclass
class DeviceInfo:
    hostname: str
    operating_system: str
    cpu_info: str
    gpu_info: str
    accel: str

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            self.hostname,
            self.operating_system,
            self.cpu_info,
            self.gpu_info,
            self.accel,
        )


def current_device_info() -> DeviceInfo:
    return DeviceInfo(
        hostname=socket.gethostname(),
        operating_system=f"{platform.system()} {platform.release()}",
        cpu_info=platform.processor() or platform.machine(),
        gpu_info="",  # TODO
        accel=get_accel(),
    )


def update_user_device(db_path: str | Path) -> int:
    """Upsert the current user_device row and return its id."""
    device_info = current_device_info()

    with get_conn(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id FROM user_device
            WHERE hostname = ? AND operating_system = ? AND cpu_info = ? AND gpu_info = ? AND accel = ?
            ORDER BY id DESC LIMIT 1
            """,
            device_info.as_tuple(),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0])

        cursor.execute(
            """
            INSERT INTO user_device (hostname, operating_system, cpu_info, gpu_info, accel)
            VALUES (?, ?, ?, ?, ?)
            """,
            device_info.as_tuple(),
        )

        if (current_device_info_id := cursor.lastrowid) is None:
            raise RuntimeError("Failed to get last row ID after inserting into user_device.")

        return int(current_device_info_id)


class DBManager:
    def __init__(self, db_path: str | Path | None):
        if db_path is None:
            raise MissingDBPathError

        self.db_path = db_path
        migrate(self.db_path)
        self.user_device_id = update_user_device(self.db_path)

    def save_llama_bench_result(self, configuration: TestConfiguration, result: LlamaBenchResult):
        """Insert a single llama-bench result row. Returns rows inserted (1 or 0)."""

        configuration_id = self.save_container_configuration(configuration)
        return self.save_llama_bench_results(configuration_id, [result])

    def save_llama_bench_configuration(self, configuration: TestConfiguration) -> int:
        """Persist a llama-bench container configuration and return its id."""
        return self.save_container_configuration(configuration)

    def save_llama_bench_results(
        self,
        configuration_id: int,
        results: Collection[LlamaBenchResult],
    ) -> int:
        """Bulk-insert llama-bench result rows sharing a configuration id."""
        if not results:
            return 0

        columns = ["test_configuration_id", *TABLE_COLUMNS]
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO llama_bench ({', '.join(columns)}) VALUES ({placeholders})"
        rows = [(configuration_id, *result.as_db_tuple()) for result in results]

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.executemany(insert_sql, rows)
        return len(rows)

    def save_container_configuration(self, configuration: TestConfiguration) -> int:
        """Insert a container_configuration row and return its id."""
        values = configuration.as_db_tuple(self.user_device_id)
        runtime_args_key = values[4] if values[4] is not None else ""

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id FROM container_configuration
                WHERE user_device_id = ?
                  AND container_image = ?
                  AND container_runtime = ?
                  AND inference_engine = ?
                  AND COALESCE(runtime_args, '') = ?
                ORDER BY id DESC LIMIT 1
                """,
                (values[0], values[1], values[2], values[3], runtime_args_key),
            )
            row = cursor.fetchone()
            if row is not None:
                return int(row[0])

            try:
                cursor.execute(
                    """
                    INSERT INTO container_configuration (
                        user_device_id, container_image, container_runtime, inference_engine, runtime_args
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    values,
                )
            except sqlite3.IntegrityError:
                cursor.execute(
                    """
                    SELECT id FROM container_configuration
                    WHERE user_device_id = ?
                      AND container_image = ?
                      AND container_runtime = ?
                      AND inference_engine = ?
                      AND COALESCE(runtime_args, '') = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (values[0], values[1], values[2], values[3], runtime_args_key),
                )
                row = cursor.fetchone()
                if row is not None:
                    return int(row[0])
                raise
            rowid = cursor.lastrowid

        if rowid is None:
            raise Exception("Should never reach here")
        return int(rowid)

    def list_benchmarks(self, limit: int | None = None, offset: int = 0) -> LlamaBenchResultCollection:
        """List benchmark results from the database."""
        query = """
            SELECT
                lb.*,
                cc.inference_engine AS engine,
                datetime(lb.created_at, 'localtime') AS created_at_display
            FROM llama_bench lb
            JOIN container_configuration cc ON lb.test_configuration_id = cc.id
            ORDER BY lb.created_at DESC, lb.id DESC
            LIMIT ? OFFSET ?
        """

        effective_limit = limit if limit is not None else -1
        effective_offset = offset if limit is not None else 0
        params = [effective_limit, effective_offset]

        with get_conn(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            items = []
            for row in rows:
                row_dict = dict(row)
                result = LlamaBenchResult(**{col: row_dict.get(col) for col in TABLE_COLUMNS})
                items.append(
                    LlamaBenchResultItem(
                        result=result,
                        id=row_dict.get("id"),
                        engine=row_dict.get("engine"),
                        created_at=row_dict.get("created_at_display") or row_dict.get("created_at"),
                    )
                )
            return LlamaBenchResultCollection(results=items)
