import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from capsulelab.db.repositories import resources as _resources_repo
from capsulelab.db.repositories.resources import ResourcesRepository as _ResourcesRepository


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
            gpus.append(
                {
                    "name": parts[0],
                    "utilization_percent": utilization,
                    "memory_used_mb": memory_used,
                    "memory_total_mb": memory_total,
                }
            )
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
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu_percent,
        "memory_used_mb": memory.used / 1024 / 1024,
        "memory_total_mb": memory.total / 1024 / 1024,
        "memory_percent": memory.percent,
        "disk_used_gb": disk.used / 1024 / 1024 / 1024,
        "disk_total_gb": disk.total / 1024 / 1024 / 1024,
        "disk_percent": (disk.used / disk.total) * 100,
    }


def store_resource_snapshot(project_id: str, resources: dict, repo: _ResourcesRepository | None = None) -> int:
    repo = repo or _resources_repo
    return repo.store_snapshot(project_id, resources)


def get_resource_history(project_id: str, limit: int = 100, repo: _ResourcesRepository | None = None) -> list[dict]:
    repo = repo or _resources_repo
    return repo.get_history(project_id, limit)


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


def get_latest_resource_snapshot(project_id: str, repo: _ResourcesRepository | None = None) -> dict | None:
    repo = repo or _resources_repo
    return repo.get_latest(project_id)
