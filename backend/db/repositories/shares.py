from __future__ import annotations

from backend.db.sqlite import get_db


class SharesRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def create(self, token: str, project_id: str, app_id: str, url: str, expires_at: str):
        with self._db() as conn:
            conn.execute(
                "INSERT INTO app_shares (token, project_id, app_id, url, expires_at) VALUES (?, ?, ?, ?, ?)",
                (token, project_id, app_id, url, expires_at),
            )

    def list(self, project_id: str, app_id: str | None = None, include_revoked: bool = False) -> list[dict]:
        clauses = ["project_id = ?"]
        params: list[object] = [project_id]
        if app_id:
            clauses.append("app_id = ?")
            params.append(app_id)
        if not include_revoked:
            clauses.append("revoked_at IS NULL")
        where = " AND ".join(clauses)
        with self._db() as conn:
            rows = conn.execute(
                f"SELECT * FROM app_shares WHERE {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, token: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM app_shares WHERE token = ?",
                (token,),
            ).fetchone()
            return dict(row) if row else None

    def bind_session(self, token: str, session_id: str) -> bool:
        with self._db() as conn:
            cursor = conn.execute(
                """
                UPDATE app_shares
                SET session_id = COALESCE(session_id, ?),
                    last_accessed_at = datetime('now')
                WHERE token = ? AND revoked_at IS NULL
                """,
                (session_id, token),
            )
            return cursor.rowcount > 0

    def touch(self, token: str) -> bool:
        with self._db() as conn:
            cursor = conn.execute(
                "UPDATE app_shares SET last_accessed_at = datetime('now') WHERE token = ? AND revoked_at IS NULL",
                (token,),
            )
            return cursor.rowcount > 0

    def revoke(self, token: str) -> bool:
        with self._db() as conn:
            cursor = conn.execute(
                "UPDATE app_shares SET revoked_at = datetime('now') WHERE token = ? AND revoked_at IS NULL",
                (token,),
            )
            return cursor.rowcount > 0

    def revoke_expired(self, now_iso: str) -> int:
        with self._db() as conn:
            cursor = conn.execute(
                "UPDATE app_shares SET revoked_at = datetime('now') WHERE revoked_at IS NULL AND expires_at <= ?",
                (now_iso,),
            )
            return cursor.rowcount
