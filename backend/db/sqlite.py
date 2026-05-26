import sqlite3
import os
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


def register_project(project_id: str, name: str, path: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO projects (id, name, path, updated_at) VALUES (?, ?, ?, datetime('now'))",
            (project_id, name, path),
        )


def remove_project(project_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM app_runtime_state WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM secrets WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM experiment_runs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM build_metadata WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM build_logs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM app_shares WHERE project_id = ?", (project_id,))
        for sid in conn.execute("SELECT id FROM resource_snapshots WHERE project_id = ?", (project_id,)).fetchall():
            conn.execute("DELETE FROM container_resources WHERE snapshot_id = ?", (sid["id"],))
            conn.execute("DELETE FROM app_resources WHERE snapshot_id = ?", (sid["id"],))
            conn.execute("DELETE FROM compose_service_resources WHERE snapshot_id = ?", (sid["id"],))
        conn.execute("DELETE FROM resource_snapshots WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def list_projects():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def set_app_state(project_id: str, app_id: str, status: str, pid: int | None = None, port: int | None = None):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM app_runtime_state WHERE project_id = ? AND app_id = ?",
            (project_id, app_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE app_runtime_state SET status=?, pid=?, port=?, started_at=CASE WHEN ?='running' THEN datetime('now') ELSE started_at END WHERE id=?",
                (status, pid, port, status, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO app_runtime_state (project_id, app_id, status, pid, port) VALUES (?, ?, ?, ?, ?)",
                (project_id, app_id, status, pid, port),
            )


def get_app_state(project_id: str, app_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM app_runtime_state WHERE project_id = ? AND app_id = ?",
            (project_id, app_id),
        ).fetchone()
        return dict(row) if row else None


def list_app_states(project_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM app_runtime_state WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def register_location(location_id: str, name: str, type_: str, host: str | None, user: str | None, project_root: str | None, runtime: str, gpu: bool):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO locations (id, name, type, host, user, project_root, runtime, gpu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (location_id, name, type_, host, user, project_root, runtime, int(gpu)),
        )


def remove_location(location_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))


def list_locations():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM locations ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_location(location_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
        return dict(row) if row else None


def get_location_by_name(name: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM locations WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def list_location_tunnels() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM location_tunnels ORDER BY proxy_port").fetchall()
        return [dict(r) for r in rows]


def get_location_tunnel(location_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM location_tunnels WHERE location_id = ?", (location_id,)).fetchone()
        return dict(row) if row else None


def set_location_tunnel(location_id: str, proxy_port: int, service_port: int):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO location_tunnels (location_id, proxy_port, service_port)
            VALUES (?, ?, ?)
            ON CONFLICT(location_id) DO UPDATE SET
                proxy_port=excluded.proxy_port,
                service_port=excluded.service_port
            """,
            (location_id, proxy_port, service_port),
        )


def set_location_override(location_id: str, override_type: str, logical_name: str, value: str):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO location_overrides (location_id, override_type, logical_name, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(location_id, override_type, logical_name) DO UPDATE SET
                value=excluded.value,
                created_at=datetime('now')
            """,
            (location_id, override_type, logical_name, value),
        )


def remove_location_override(location_id: str, override_type: str, logical_name: str):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM location_overrides WHERE location_id = ? AND override_type = ? AND logical_name = ?",
            (location_id, override_type, logical_name),
        )


def list_location_overrides(location_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM location_overrides WHERE location_id = ? ORDER BY override_type, logical_name",
            (location_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_location_override(location_id: str, override_type: str, logical_name: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM location_overrides WHERE location_id = ? AND override_type = ? AND logical_name = ?",
            (location_id, override_type, logical_name),
        ).fetchone()
        return dict(row) if row else None


def clear_app_states(project_id: str):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM app_runtime_state WHERE project_id = ?",
            (project_id,),
        )


def set_secret(project_id: str, name: str, value: str, location: str | None = None):
    location_key = location or ""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO secrets (project_id, name, location, value, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(project_id, name, location) DO UPDATE SET
                value=excluded.value,
                updated_at=datetime('now')
            """,
            (project_id, name, location_key, value),
        )


def remove_secret(project_id: str, name: str, location: str | None = None):
    location_key = location or ""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM secrets WHERE project_id = ? AND name = ? AND COALESCE(location, '') = ?",
            (project_id, name, location_key),
        )


def list_secrets(project_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT project_id, name, NULLIF(location, '') AS location, updated_at FROM secrets WHERE project_id = ? ORDER BY name, location",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_secret(project_id: str, name: str, location: str | None = None):
    location_key = location or ""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM secrets WHERE project_id = ? AND name = ? AND COALESCE(location, '') = ? LIMIT 1",
            (project_id, name, location_key),
        ).fetchone()
        return dict(row) if row else None


def create_run(run_id: str, project_id: str, name: str, notes: str | None = None, artifact_path: str | None = None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO experiment_runs (id, project_id, name, notes, artifact_path) VALUES (?, ?, ?, ?, ?)",
            (run_id, project_id, name, notes, artifact_path),
        )


def finish_run(run_id: str, status: str = "finished", project_id: str | None = None):
    with get_db() as conn:
        if project_id:
            conn.execute(
                "UPDATE experiment_runs SET status = ?, ended_at = datetime('now') WHERE id = ? AND project_id = ?",
                (status, run_id, project_id),
            )
        else:
            conn.execute(
                "UPDATE experiment_runs SET status = ?, ended_at = datetime('now') WHERE id = ?",
                (status, run_id),
            )


def list_runs(project_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_runs WHERE project_id = ? ORDER BY started_at DESC",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_build_metadata(project_id: str, image: str, image_id: str | None = None, digest: str | None = None):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO build_metadata (project_id, image, image_id, digest, built_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(project_id) DO UPDATE SET
                image=excluded.image,
                image_id=excluded.image_id,
                digest=excluded.digest,
                built_at=datetime('now')
            """,
            (project_id, image, image_id, digest),
        )


def get_build_metadata(project_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM build_metadata WHERE project_id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def add_build_log(project_id: str, image: str, status: str, logs: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO build_logs (project_id, image, status, logs) VALUES (?, ?, ?, ?)",
            (project_id, image, status, logs),
        )


def get_build_logs(project_id: str, limit: int = 5) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM build_logs WHERE project_id = ? ORDER BY built_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def create_app_share(token: str, project_id: str, app_id: str, url: str, expires_at: str):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO app_shares (token, project_id, app_id, url, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, project_id, app_id, url, expires_at),
        )


def list_app_shares(project_id: str, app_id: str | None = None, include_revoked: bool = False) -> list[dict]:
    clauses = ["project_id = ?"]
    params: list[object] = [project_id]
    if app_id:
        clauses.append("app_id = ?")
        params.append(app_id)
    if not include_revoked:
        clauses.append("revoked_at IS NULL")
    where = " AND ".join(clauses)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM app_shares WHERE {where} ORDER BY created_at DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_app_share(token: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE app_shares SET revoked_at = datetime('now') WHERE token = ? AND revoked_at IS NULL",
            (token,),
        )
        return cursor.rowcount > 0
