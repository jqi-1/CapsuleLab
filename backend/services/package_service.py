import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from backend.db.sqlite import get_build_metadata, list_projects, get_project
from backend.services import project_service, git_service


def export_project(project_id: str, output_path: str | None = None) -> str:
    row = get_project(project_id)
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
        shutil.copytree(project_path, export_path, symlinks=True,
                        ignore=shutil.ignore_patterns(
                            ".git", "__pycache__", "*.pyc", ".venv", "venv",
                            ".cursor", ".windsurf", ".trash",
                        ))

        build_meta = get_build_metadata(project_id)
        manifest = {
            "capsule_version": "1.0",
            "exported_at": timestamp,
            "project_name": config.name,
            "project_description": config.description or "",
            "project_id": project_id,
            "config": config.model_dump(),
            "build_metadata": build_meta,
            "includes_git": (project_path / ".git").exists(),
        }
        (export_path / ".capsule-manifest.json").write_text(json.dumps(manifest, indent=2))

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
            tar.extractall(path=tmp)

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

        result = git_service.register_existing(str(target), name=project_name, scaffold=False)
        result["manifest"] = manifest
        result["path"] = str(target)
        return result
