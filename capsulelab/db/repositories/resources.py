from __future__ import annotations

from capsulelab.db.sqlite import get_db


class ResourcesRepository:
    def __init__(self, db_provider=None):
        self._db = db_provider or get_db

    def store_snapshot(self, project_id: str, resources: dict) -> int:
        with self._db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO resource_snapshots
                (project_id, cpu_percent, memory_used_mb, memory_total_mb, memory_percent,
                 disk_used_gb, disk_total_gb, disk_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    resources.get("cpu_percent"),
                    resources.get("memory_used_mb"),
                    resources.get("memory_total_mb"),
                    resources.get("memory_percent"),
                    resources.get("disk_used_gb"),
                    resources.get("disk_total_gb"),
                    resources.get("disk_percent"),
                ),
            )
            snapshot_id = cursor.lastrowid or 0

            for container in resources.get("containers") or []:
                conn.execute(
                    """
                    INSERT INTO container_resources
                    (snapshot_id, container_name, cpu_percent, memory_used_mb, memory_limit_mb,
                     memory_percent, network_rx_bytes, network_tx_bytes, block_read_bytes, block_write_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        container.get("name"),
                        container.get("cpu_percent"),
                        container.get("memory_used_mb"),
                        container.get("memory_limit_mb"),
                        container.get("memory_percent"),
                        container.get("network_rx_bytes", 0),
                        container.get("network_tx_bytes", 0),
                        container.get("block_read_bytes", 0),
                        container.get("block_write_bytes", 0),
                    ),
                )

            for app in resources.get("apps") or []:
                conn.execute(
                    """
                    INSERT INTO app_resources
                    (snapshot_id, app_id, app_name, cpu_percent, memory_used_mb, memory_limit_mb, memory_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        app.get("id"),
                        app.get("name"),
                        app.get("cpu_percent", 0),
                        app.get("memory_used_mb", 0),
                        app.get("memory_limit_mb", 0),
                        app.get("memory_percent", 0),
                    ),
                )

            for service in resources.get("compose_services") or []:
                conn.execute(
                    """
                    INSERT INTO compose_service_resources
                    (snapshot_id, service_name, cpu_percent, memory_used_mb, memory_limit_mb,
                     memory_percent, network_rx_bytes, network_tx_bytes, health_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        service.get("name"),
                        service.get("cpu_percent", 0),
                        service.get("memory_used_mb", 0),
                        service.get("memory_limit_mb", 0),
                        service.get("memory_percent", 0),
                        service.get("network_rx_bytes", 0),
                        service.get("network_tx_bytes", 0),
                        service.get("health_status", "unknown"),
                    ),
                )

            return snapshot_id

    def get_history(self, project_id: str, limit: int = 100) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM resource_snapshots WHERE project_id = ? ORDER BY timestamp DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()

            history = []
            for row in rows:
                snapshot = dict(row)
                snapshot["containers"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM container_resources WHERE snapshot_id = ?", (snapshot["id"],)
                    ).fetchall()
                ]
                snapshot["apps"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM app_resources WHERE snapshot_id = ?", (snapshot["id"],)
                    ).fetchall()
                ]
                snapshot["compose_services"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM compose_service_resources WHERE snapshot_id = ?", (snapshot["id"],)
                    ).fetchall()
                ]
                history.append(snapshot)

            return history

    def get_latest(self, project_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM resource_snapshots WHERE project_id = ? ORDER BY timestamp DESC LIMIT 1",
                (project_id,),
            ).fetchone()

            if not row:
                return None

            snapshot = dict(row)
            snapshot["containers"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM container_resources WHERE snapshot_id = ?", (snapshot["id"],)
                ).fetchall()
            ]
            snapshot["apps"] = [
                dict(r)
                for r in conn.execute("SELECT * FROM app_resources WHERE snapshot_id = ?", (snapshot["id"],)).fetchall()
            ]
            snapshot["compose_services"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM compose_service_resources WHERE snapshot_id = ?", (snapshot["id"],)
                ).fetchall()
            ]

            return snapshot
