from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent

SCHEMA = Path(__file__).resolve().parent.parent.parent / "capsulelab" / "db" / "schema.sql"


def _default_schema() -> str:
    if SCHEMA.exists():
        return SCHEMA.read_text()
    return dedent("""\
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS app_runtime_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            app_id TEXT NOT NULL,
            pid INTEGER,
            status TEXT NOT NULL DEFAULT 'stopped',
            port INTEGER,
            started_at TEXT
        );
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            location TEXT,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(project_id, name, location)
        );
        CREATE TABLE IF NOT EXISTS build_metadata (
            project_id TEXT PRIMARY KEY,
            image TEXT NOT NULL,
            image_id TEXT,
            digest TEXT,
            built_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS build_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            image TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unknown',
            logs TEXT NOT NULL DEFAULT '',
            built_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS experiment_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            notes TEXT,
            artifact_path TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            ended_at TEXT
        );
        CREATE TABLE IF NOT EXISTS app_shares (
            token TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            app_id TEXT NOT NULL,
            url TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            session_id TEXT,
            last_accessed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            revoked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS locations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'ssh',
            host TEXT,
            user TEXT,
            project_root TEXT,
            runtime TEXT NOT NULL DEFAULT 'docker',
            gpu INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS location_tunnels (
            location_id TEXT PRIMARY KEY,
            proxy_port INTEGER NOT NULL,
            service_port INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS location_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id TEXT NOT NULL,
            override_type TEXT NOT NULL CHECK(override_type IN ('dataset', 'cache', 'secret')),
            logical_name TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(location_id, override_type, logical_name)
        );
        CREATE TABLE IF NOT EXISTS resource_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            cpu_percent REAL,
            memory_used_mb REAL,
            memory_total_mb REAL,
            memory_percent REAL,
            disk_used_gb REAL,
            disk_total_gb REAL,
            disk_percent REAL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS container_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            container_name TEXT NOT NULL,
            cpu_percent REAL,
            memory_used_mb REAL,
            memory_limit_mb REAL,
            memory_percent REAL,
            network_rx_bytes REAL,
            network_tx_bytes REAL,
            block_read_bytes REAL,
            block_write_bytes REAL
        );
        CREATE TABLE IF NOT EXISTS app_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            app_id TEXT NOT NULL,
            app_name TEXT,
            cpu_percent REAL,
            memory_used_mb REAL,
            memory_limit_mb REAL,
            memory_percent REAL
        );
        CREATE TABLE IF NOT EXISTS compose_service_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            cpu_percent REAL,
            memory_used_mb REAL,
            memory_limit_mb REAL,
            memory_percent REAL,
            network_rx_bytes REAL,
            network_tx_bytes REAL,
            health_status TEXT
        );
    """)


def in_memory_db_provider(schema: str | None = None) -> Callable:
    import sqlite3

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema or _default_schema())
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA foreign_keys=ON")

    @contextmanager
    def provider():
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    return provider
