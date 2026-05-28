from __future__ import annotations

from capsulelab.db.sqlite import get_db


class ProjectsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def get(self, project_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def list(self) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def register(self, project_id: str, name: str, path: str):
        with self._db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects (id, name, path, updated_at) VALUES (?, ?, ?, datetime('now'))",
                (project_id, name, path),
            )

    def remove(self, project_id: str):
        with self._db() as conn:
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
