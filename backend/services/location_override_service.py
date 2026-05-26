from pathlib import Path
from backend.db import sqlite
from backend.models.project import ProjectConfig, Dataset, Mount, Cache


def resolve_dataset_path(dataset: Dataset, location_id: str | None, project_path: str) -> str:
    if location_id:
        override = sqlite.get_location_override(location_id, "dataset", dataset.name)
        if override:
            return override["value"]
    if Path(dataset.path).is_absolute():
        return dataset.path
    return str(Path(project_path) / dataset.path)


def resolve_cache_path(cache: Cache, location_id: str | None) -> str:
    if location_id:
        override = sqlite.get_location_override(location_id, "cache", cache.source)
        if override:
            return override["value"]
    return str(Path(cache.source).expanduser())


def resolve_secret_location(secret_name: str, location_id: str | None) -> str | None:
    if not location_id:
        return None
    override = sqlite.get_location_override(location_id, "secret", secret_name)
    if override:
        return override["value"]
    return None


def apply_location_overrides(
    config: ProjectConfig,
    project_path: str,
    location_id: str | None = None,
) -> dict:
    resolved = {
        "mounts": [],
        "datasets": [],
        "caches": [],
        "secrets": [],
    }
    for m in config.mounts:
        resolved["mounts"].append({
            "source": str(Path(project_path) / m.source) if not Path(m.source).is_absolute() else m.source,
            "target": m.target,
            "read_only": m.read_only,
        })
    for dataset in config.datasets:
        resolved_path = resolve_dataset_path(dataset, location_id, project_path)
        resolved["datasets"].append({
            "name": dataset.name,
            "path": resolved_path,
            "target": dataset.target,
            "read_only": dataset.read_only,
        })
    for cache in config.caches:
        resolved_path = resolve_cache_path(cache, location_id)
        resolved["caches"].append({
            "source": resolved_path,
            "target": cache.target,
        })
    for secret in config.secrets:
        resolved["secrets"].append({
            "name": secret.name,
            "location": resolve_secret_location(secret.name, location_id) or secret.location,
            "required": secret.required,
        })
    return resolved
