import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_DIR = Path.home() / ".capsulelab"
DB_PATH = DB_DIR / "capsulelab.db"


@contextmanager
def get_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
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
                started_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
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

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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

            CREATE TABLE IF NOT EXISTS experiment_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                notes TEXT,
                artifact_path TEXT,
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                ended_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS build_metadata (
                project_id TEXT PRIMARY KEY,
                image TEXT NOT NULL,
                image_id TEXT,
                digest TEXT,
                built_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS build_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                image TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unknown',
                logs TEXT NOT NULL DEFAULT '',
                built_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
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
                revoked_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS location_tunnels (
                location_id TEXT PRIMARY KEY,
                proxy_port INTEGER NOT NULL,
                service_port INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (location_id) REFERENCES locations(id)
            );

            CREATE TABLE IF NOT EXISTS location_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT NOT NULL,
                override_type TEXT NOT NULL CHECK(override_type IN ('dataset', 'cache', 'secret')),
                logical_name TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (location_id) REFERENCES locations(id),
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
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
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
                block_write_bytes REAL,
                FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
            );

            CREATE TABLE IF NOT EXISTS app_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                app_id TEXT NOT NULL,
                app_name TEXT,
                cpu_percent REAL,
                memory_used_mb REAL,
                memory_limit_mb REAL,
                memory_percent REAL,
                FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
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
                health_status TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
            );
        """)
        _ensure_column(conn, "app_shares", "session_id", "TEXT")
        _ensure_column(conn, "app_shares", "last_accessed_at", "TEXT")


def _ensure_column(conn, table: str, column: str, definition: str):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if column not in {row["name"] for row in rows}:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
