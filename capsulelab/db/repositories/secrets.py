from __future__ import annotations

from capsulelab.db.sqlite import get_db


class SecretsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def set(self, project_id: str, name: str, value: str, location: str | None = None):
        location_key = location or ""
        with self._db() as conn:
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

    def remove(self, project_id: str, name: str, location: str | None = None):
        location_key = location or ""
        with self._db() as conn:
            conn.execute(
                "DELETE FROM secrets WHERE project_id = ? AND name = ? AND COALESCE(location, '') = ?",
                (project_id, name, location_key),
            )

    def list(self, project_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                (
                    "SELECT project_id, name, NULLIF(location, '') AS location, updated_at "
                    "FROM secrets WHERE project_id = ? ORDER BY name, location"
                ),
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, project_id: str, name: str, location: str | None = None) -> dict | None:
        location_key = location or ""
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM secrets WHERE project_id = ? AND name = ? AND COALESCE(location, '') = ? LIMIT 1",
                (project_id, name, location_key),
            ).fetchone()
            return dict(row) if row else None
