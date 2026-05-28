from __future__ import annotations

from capsulelab.db.sqlite import get_db


class BuildsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def set_metadata(self, project_id: str, image: str, image_id: str | None = None, digest: str | None = None):
        with self._db() as conn:
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

    def get_metadata(self, project_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM build_metadata WHERE project_id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def add_log(self, project_id: str, image: str, status: str, logs: str):
        with self._db() as conn:
            conn.execute(
                "INSERT INTO build_logs (project_id, image, status, logs) VALUES (?, ?, ?, ?)",
                (project_id, image, status, logs),
            )

    def get_logs(self, project_id: str, limit: int = 5) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM build_logs WHERE project_id = ? ORDER BY built_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
