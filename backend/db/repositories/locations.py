from __future__ import annotations

from backend.db.sqlite import get_db


class LocationsRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def register(self, location_id: str, name: str, type_: str, host: str | None, user: str | None, project_root: str | None, runtime: str, gpu: bool):
        with self._db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO locations (id, name, type, host, user, project_root, runtime, gpu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (location_id, name, type_, host, user, project_root, runtime, int(gpu)),
            )

    def remove(self, location_id: str):
        with self._db() as conn:
            conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))

    def list(self) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM locations ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, location_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM locations WHERE id = ?", (location_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_name(self, name: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM locations WHERE name = ?", (name,)
            ).fetchone()
            return dict(row) if row else None

    def list_tunnels(self) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM location_tunnels ORDER BY proxy_port"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_tunnel(self, location_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM location_tunnels WHERE location_id = ?", (location_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_tunnel(self, location_id: str, proxy_port: int, service_port: int):
        with self._db() as conn:
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

    def set_override(self, location_id: str, override_type: str, logical_name: str, value: str):
        with self._db() as conn:
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

    def remove_override(self, location_id: str, override_type: str, logical_name: str):
        with self._db() as conn:
            conn.execute(
                "DELETE FROM location_overrides WHERE location_id = ? AND override_type = ? AND logical_name = ?",
                (location_id, override_type, logical_name),
            )

    def list_overrides(self, location_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM location_overrides WHERE location_id = ? ORDER BY override_type, logical_name",
                (location_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_override(self, location_id: str, override_type: str, logical_name: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM location_overrides WHERE location_id = ? AND override_type = ? AND logical_name = ?",
                (location_id, override_type, logical_name),
            ).fetchone()
            return dict(row) if row else None
