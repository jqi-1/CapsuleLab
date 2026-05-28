from __future__ import annotations

from capsulelab.db.sqlite import get_db


class AppsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def set_state(self, project_id: str, app_id: str, status: str, pid: int | None = None, port: int | None = None):
        with self._db() as conn:
            existing = conn.execute(
                "SELECT id FROM app_runtime_state WHERE project_id = ? AND app_id = ?",
                (project_id, app_id),
            ).fetchone()
            if existing:
                conn.execute(
                    (
                        "UPDATE app_runtime_state SET status=?, pid=?, port=?, "
                        "started_at=CASE WHEN ?='running' THEN datetime('now') ELSE started_at END "
                        "WHERE id=?"
                    ),
                    (status, pid, port, status, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO app_runtime_state (project_id, app_id, status, pid, port) VALUES (?, ?, ?, ?, ?)",
                    (project_id, app_id, status, pid, port),
                )

    def get_state(self, project_id: str, app_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM app_runtime_state WHERE project_id = ? AND app_id = ?",
                (project_id, app_id),
            ).fetchone()
            return dict(row) if row else None

    def list_states(self, project_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM app_runtime_state WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_states(self, project_id: str):
        with self._db() as conn:
            conn.execute(
                "DELETE FROM app_runtime_state WHERE project_id = ?",
                (project_id,),
            )
