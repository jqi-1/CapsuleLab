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

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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
