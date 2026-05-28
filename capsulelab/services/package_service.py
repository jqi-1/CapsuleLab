import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from capsulelab.db.repositories import builds, projects
from capsulelab.services import project_import_service, project_service

EXCLUDED_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    ".venv",
    "venv",
    ".cursor",
    ".windsurf",
    ".trash",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
]


def export_project(project_id: str, output_path: str | None = None) -> str:
    row = projects.get(project_id)
    if not row:
        raise ValueError(f"Project '{project_id}' not found")
    project_path = Path(row["path"])
    config = project_service.load_config(str(project_path))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    capsule_name = f"{config.name}-capsule-{timestamp}.tar.gz"
    dest = Path(output_path or Path.cwd()) / capsule_name

    with tempfile.TemporaryDirectory(prefix="capsulelab-export-") as tmpdir:
        tmp = Path(tmpdir)
        export_path = tmp / config.name
        shutil.copytree(project_path, export_path, symlinks=True, ignore=shutil.ignore_patterns(*EXCLUDED_PATTERNS))

        build_meta = builds.get_metadata(project_id)
        sanitized_config, redactions = sanitize_config_for_export(config, project_path)
        config_path = export_path / project_service.WORKBENCH_DIR / project_service.CONFIG_FILE
        if config_path.exists():
            config_path.write_text(yaml.safe_dump(sanitized_config, sort_keys=False))
        manifest = {
            "capsule_version": "1.0",
            "exported_at": timestamp,
            "project_name": config.name,
            "project_description": config.description or "",
            "project_id": project_id,
            "config": sanitized_config,
            "build_metadata": build_meta,
            "includes_git": (project_path / ".git").exists(),
            "excluded_patterns": EXCLUDED_PATTERNS,
            "redactions": redactions,
        }
        (export_path / ".capsule-manifest.json").write_text(json.dumps(manifest, indent=2))
        (export_path / ".capsule-export-report.json").write_text(
            json.dumps(
                {
                    "policy": (
                        "portable project intent only; local secrets and "
                        "machine-specific paths are excluded or redacted"
                    ),
                    "redactions": redactions,
                    "excluded_patterns": EXCLUDED_PATTERNS,
                },
                indent=2,
            )
        )

        with tarfile.open(str(dest), "w:gz") as tar:
            tar.add(export_path, arcname=config.name)

    return str(dest)


def import_project(capsule_path: str, dest_dir: str | None = None) -> dict:
    capsule = Path(capsule_path)
    if not capsule.exists():
        raise FileNotFoundError(f"Capsule not found: {capsule_path}")
    if not tarfile.is_tarfile(capsule_path):
        raise ValueError(f"Not a valid capsule archive: {capsule_path}")

    dest = Path(dest_dir or Path.cwd())
    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="capsulelab-import-") as tmpdir:
        tmp = Path(tmpdir)
        with tarfile.open(capsule_path, "r:gz") as tar:
            _safe_extract(tar, tmp)

        items = list(tmp.iterdir())
        if not items:
            raise ValueError("Capsule archive is empty")
        project_root = items[0]

        manifest_path = project_root / ".capsule-manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        else:
            manifest = {}

        target = dest / project_root.name
        if target.exists():
            raise FileExistsError(f"Target directory already exists: {target}")
        shutil.copytree(project_root, target)

        config_path = target / project_service.WORKBENCH_DIR / project_service.CONFIG_FILE
        project_name = manifest.get("project_name", target.name)
        if config_path.exists():
            config_data = yaml.safe_load(config_path.read_text()) or {}
            project_name = config_data.get("name", target.name)

        result = project_import_service.register_existing(str(target), name=project_name, scaffold=False)
        result["manifest"] = manifest
        result["path"] = str(target)
        return result


def sanitize_config_for_export(config, project_path: Path) -> tuple[dict, list[dict]]:
    data = config.model_dump(mode="json")
    redactions: list[dict] = []
    project_path = project_path.resolve()

    for key in list((data.get("environment") or {}).keys()):
        value = data["environment"][key]
        if value:
            data["environment"][key] = ""
            redactions.append({"field": f"environment.{key}", "reason": "environment values are local or sensitive"})

    for mount in data.get("mounts") or []:
        source = mount.get("source", "")
        if _is_machine_specific_path(source, project_path):
            mount["source"] = ""
            redactions.append(
                {
                    "field": f"mounts.{mount.get('target', '')}.source",
                    "reason": f"machine-specific path redacted: {source}",
                }
            )

    for dataset in data.get("datasets") or []:
        source = dataset.get("path", "")
        if _is_machine_specific_path(source, project_path):
            dataset["path"] = ""
            redactions.append(
                {
                    "field": f"datasets.{dataset.get('name', '')}.path",
                    "reason": f"machine-specific path redacted: {source}",
                }
            )

    for cache in data.get("caches") or []:
        source = cache.get("source", "")
        if _is_machine_specific_path(source, project_path):
            cache["source"] = ""
            redactions.append(
                {
                    "field": f"caches.{cache.get('target', '')}.source",
                    "reason": f"machine-specific path redacted: {source}",
                }
            )

    for secret in data.get("secrets") or []:
        if secret.get("location"):
            secret["location"] = None
            redactions.append(
                {"field": f"secrets.{secret.get('name', '')}.location", "reason": "secret locations are local state"}
            )

    return data, redactions


def _is_machine_specific_path(value: str, project_path: Path) -> bool:
    if not value:
        return False
    path = Path(value).expanduser()
    if not path.is_absolute():
        return False
    try:
        path.resolve().relative_to(project_path)
        return False
    except ValueError:
        return True


def _safe_extract(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in tar.getmembers():
        target = (destination / member.name).resolve()
        if destination not in [target, *target.parents]:
            raise ValueError(f"Unsafe archive member path: {member.name}")
        if member.issym() or member.islnk():
            link_target = (target.parent / member.linkname).resolve()
            if destination not in [link_target, *link_target.parents]:
                raise ValueError(f"Unsafe archive link target: {member.name}")
    tar.extractall(path=destination)
