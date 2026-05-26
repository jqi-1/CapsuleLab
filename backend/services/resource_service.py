import shutil
import subprocess
from pathlib import Path
from backend.db.sqlite import get_db
from backend.services import project_service
import json
from datetime import datetime


def _psutil():
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError(
            "psutil is required for live system resource metrics. Install project dependencies with `pip install -e .`."
        ) from exc
    return psutil


def disk_status(path: str) -> dict:
    usage = shutil.disk_usage(path)
    return {
        "path": str(Path(path).resolve()),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": round((usage.free / usage.total) * 100, 2) if usage.total else 0,
    }


def gpu_status() -> dict:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "gpus": []}
    if result.returncode != 0:
        return {"available": False, "gpus": []}
    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 4:
            try:
                utilization = int(parts[1])
                memory_used = int(parts[2])
                memory_total = int(parts[3])
            except ValueError:
                utilization = 0
                memory_used = 0
                memory_total = 0
            gpus.append({
                "name": parts[0],
                "utilization_percent": utilization,
                "memory_used_mb": memory_used,
                "memory_total_mb": memory_total,
            })
    return {"available": bool(gpus), "gpus": gpus}


def project_resources(project_path: str) -> dict:
    return {
        "disk": disk_status(project_path),
        "gpu": gpu_status(),
    }


def get_system_resources() -> dict:
    """Get current system resource usage"""
    psutil = _psutil()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return {
        "cpu_percent": cpu_percent,
        "memory_used_mb": memory.used / 1024 / 1024,
        "memory_total_mb": memory.total / 1024 / 1024,
        "memory_percent": memory.percent,
        "disk_used_gb": disk.used / 1024 / 1024 / 1024,
        "disk_total_gb": disk.total / 1024 / 1024 / 1024,
        "disk_percent": (disk.used / disk.total) * 100
    }


def store_resource_snapshot(project_id: str, resources: dict) -> int:
    """Store a resource snapshot for historical tracking"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO resource_snapshots
            (project_id, cpu_percent, memory_used_mb, memory_total_mb, memory_percent,
             disk_used_gb, disk_total_gb, disk_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            resources.get("cpu_percent"),
            resources.get("memory_used_mb"),
            resources.get("memory_total_mb"),
            resources.get("memory_percent"),
            resources.get("disk_used_gb"),
            resources.get("disk_total_gb"),
            resources.get("disk_percent")
        ))
        snapshot_id = cursor.lastrowid
        if snapshot_id is None:
            # This should never happen with a successful INSERT, but handle just in case
            snapshot_id = 0

        # Store container resources if available
        if "containers" in resources:
            for container in resources["containers"]:
                conn.execute("""
                    INSERT INTO container_resources
                    (snapshot_id, container_name, cpu_percent, memory_used_mb, memory_limit_mb,
                     memory_percent, network_rx_bytes, network_tx_bytes, block_read_bytes, block_write_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    container.get("name"),
                    container.get("cpu_percent"),
                    container.get("memory_used_mb"),
                    container.get("memory_limit_mb"),
                    container.get("memory_percent"),
                    container.get("network_rx_bytes", 0),
                    container.get("network_tx_bytes", 0),
                    container.get("block_read_bytes", 0),
                    container.get("block_write_bytes", 0)
                ))

        # Store app resources if available
        if "apps" in resources:
            for app in resources["apps"]:
                conn.execute("""
                    INSERT INTO app_resources
                    (snapshot_id, app_id, app_name, cpu_percent, memory_used_mb, memory_limit_mb, memory_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    app.get("id"),
                    app.get("name"),
                    app.get("cpu_percent", 0),
                    app.get("memory_used_mb", 0),
                    app.get("memory_limit_mb", 0),
                    app.get("memory_percent", 0)
                ))

        # Store compose service resources if available
        if "compose_services" in resources:
            for service in resources["compose_services"]:
                conn.execute("""
                    INSERT INTO compose_service_resources
                    (snapshot_id, service_name, cpu_percent, memory_used_mb, memory_limit_mb,
                     memory_percent, network_rx_bytes, network_tx_bytes, health_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    service.get("name"),
                    service.get("cpu_percent", 0),
                    service.get("memory_used_mb", 0),
                    service.get("memory_limit_mb", 0),
                    service.get("memory_percent", 0),
                    service.get("network_rx_bytes", 0),
                    service.get("network_tx_bytes", 0),
                    service.get("health_status", "unknown")
                ))

        return snapshot_id


def get_resource_history(project_id: str, limit: int = 100) -> list[dict]:
    """Get resource history for a project"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM resource_snapshots
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (project_id, limit)).fetchall()

        history = []
        for row in rows:
            snapshot = dict(row)

            # Get container resources for this snapshot
            container_rows = conn.execute("""
                SELECT * FROM container_resources WHERE snapshot_id = ?
            """, (snapshot["id"],)).fetchall()
            snapshot["containers"] = [dict(r) for r in container_rows]

            # Get app resources for this snapshot
            app_rows = conn.execute("""
                SELECT * FROM app_resources WHERE snapshot_id = ?
            """, (snapshot["id"],)).fetchall()
            snapshot["apps"] = [dict(r) for r in app_rows]

            # Get compose service resources for this snapshot
            compose_rows = conn.execute("""
                SELECT * FROM compose_service_resources WHERE snapshot_id = ?
            """, (snapshot["id"],)).fetchall()
            snapshot["compose_services"] = [dict(r) for r in compose_rows]

            history.append(snapshot)

        return history


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


def get_latest_resource_snapshot(project_id: str) -> dict | None:
    """Get the most recent resource snapshot for a project"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM resource_snapshots
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (project_id,)).fetchone()

        if not row:
            return None

        snapshot = dict(row)

        # Get container resources for this snapshot
        container_rows = conn.execute("""
            SELECT * FROM container_resources WHERE snapshot_id = ?
        """, (snapshot["id"],)).fetchall()
        snapshot["containers"] = [dict(r) for r in container_rows]

        # Get app resources for this snapshot
        app_rows = conn.execute("""
            SELECT * FROM app_resources WHERE snapshot_id = ?
        """, (snapshot["id"],)).fetchall()
        snapshot["apps"] = [dict(r) for r in app_rows]

        # Get compose service resources for this snapshot
        compose_rows = conn.execute("""
            SELECT * FROM compose_service_resources WHERE snapshot_id = ?
        """, (snapshot["id"],)).fetchall()
        snapshot["compose_services"] = [dict(r) for r in compose_rows]

        return snapshot
