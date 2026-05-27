from __future__ import annotations

from backend.db.sqlite import get_db


class RunsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def create(self, run_id: str, project_id: str, name: str, notes: str | None = None, artifact_path: str | None = None):
        with self._db() as conn:
            conn.execute(
                "INSERT INTO experiment_runs (id, project_id, name, notes, artifact_path) VALUES (?, ?, ?, ?, ?)",
                (run_id, project_id, name, notes, artifact_path),
            )

    def finish(self, run_id: str, status: str = "finished", project_id: str | None = None):
        with self._db() as conn:
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

    def list(self, project_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM experiment_runs WHERE project_id = ? ORDER BY started_at DESC",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]
