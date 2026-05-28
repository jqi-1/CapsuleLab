import os
import shutil
from pathlib import Path

import yaml

from capsulelab.core.project import ProjectConfig, ProjectMode, default_presets

WORKBENCH_DIR = ".workbench"
CONFIG_FILE = "project.yaml"
CAPSULE_CONFIG_FILE = "capsule.yaml"
CURRENT_SCHEMA_VERSION = 1


def config_path(project_path: str) -> Path:
    return Path(project_path) / WORKBENCH_DIR / CONFIG_FILE


def capsule_config_path(project_path: str) -> Path:
    return Path(project_path) / CAPSULE_CONFIG_FILE


def discover_config_path(project_path: str) -> Path:
    canonical = config_path(project_path)
    if canonical.exists():
        return canonical
    capsule = capsule_config_path(project_path)
    if capsule.exists():
        return capsule
    return canonical


def load_config(project_path: str) -> ProjectConfig:
    path = discover_config_path(project_path)
    if not path.exists():
        raise FileNotFoundError(f"Project config not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data:
        raise ValueError(f"Empty or invalid YAML in {path}")
    data = migrate_config_data(data)
    cfg = ProjectConfig(**data)
    if cfg.mode and not cfg.presets:
        cfg.presets = default_presets(cfg.mode)
    return cfg


def migrate_config_data(data: dict) -> dict:
    migrated = dict(data)
    version = int(migrated.get("schema_version") or 1)
    if version > CURRENT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported project config schema_version {version}")
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    return migrated


def write_config(project_path: str, config: ProjectConfig | dict) -> Path:
    path = config_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json") if isinstance(config, ProjectConfig) else migrate_config_data(config)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def migrate_manifest(project_path: str, write_capsule_copy: bool = True) -> dict:
    source = discover_config_path(project_path)
    if not source.exists():
        raise FileNotFoundError(f"Project config not found at {source}")
    config = load_config(project_path)
    canonical = write_config(project_path, config)
    capsule = capsule_config_path(project_path)
    wrote_capsule = False
    if write_capsule_copy:
        capsule.write_text(yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False))
        wrote_capsule = True
    return {
        "source": str(source),
        "canonical": str(canonical),
        "capsule": str(capsule) if wrote_capsule else None,
        "schema_version": config.schema_version,
    }


def validate(config: ProjectConfig, project_path: str | None = None) -> list[str]:
    warnings: list[str] = []
    if not config.name.strip():
        warnings.append("Project name is empty")
    if config.runtime.type.value == "docker":
        df_path = Path(project_path or ".") / config.runtime.dockerfile
        if not df_path.exists():
            warnings.append(f"Dockerfile not found at {config.runtime.dockerfile}")
    for app in config.apps:
        if app.kind == "web" and app.port is None:
            warnings.append(f"App '{app.id}' is a web app but has no port")
        if app.port is not None and (app.port < 1 or app.port > 65535):
            warnings.append(f"App '{app.id}' has invalid port {app.port}")
    for dataset in config.datasets:
        if not dataset.name.strip():
            warnings.append("Dataset name is empty")
        if not dataset.path.strip():
            warnings.append(f"Dataset '{dataset.name}' has empty path")

    if config.mode == ProjectMode.deployable:
        p = Path(project_path or ".")
        if not (p / "tests").exists():
            warnings.append("Deployable mode: tests/ directory not found")
        if config.runtime.type.value != "docker":
            warnings.append(f"Deployable mode: runtime type should be 'docker', got '{config.runtime.type.value}'")
    elif config.mode == ProjectMode.opensource:
        p = Path(project_path or ".")
        for required in ["README.md", "LICENSE", "CONTRIBUTING.md"]:
            if not (p / required).exists():
                warnings.append(f"Open-source mode: {required} not found")
    elif config.mode == ProjectMode.research:
        p = Path(project_path or ".")
        if not (p / "notebooks").exists():
            warnings.append("Research mode: notebooks/ directory not found")

    return warnings


def create_from_template(name: str, template_path: str, dest_path: str, image_name: str | None = None) -> str:
    dest = Path(dest_path)
    if dest.exists():
        raise FileExistsError(f"Destination {dest_path} already exists")
    src = Path(template_path)
    if not src.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    shutil.copytree(src, dest)
    path = config_path(str(dest))
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f)
        config["name"] = name
        config["schema_version"] = CURRENT_SCHEMA_VERSION
        if image_name:
            config["runtime"]["image"] = image_name
        elif "image" in config.get("runtime", {}):
            config["runtime"]["image"] = f"{name}:dev"
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    from capsulelab.services.git_service import init_repo

    init_repo(str(dest))
    return str(dest)


def find_projects(base_dir: str | None = None) -> list[dict]:
    if base_dir is None:
        base_dir = os.getcwd()
    projects = []
    base = Path(base_dir)
    for child in base.iterdir():
        if child.is_dir():
            path = discover_config_path(str(child))
            if path.exists():
                try:
                    cfg = load_config(str(child))
                    projects.append(
                        {
                            "name": cfg.name,
                            "path": str(child),
                            "config": cfg,
                        }
                    )
                except Exception:
                    pass
    return projects


def get_project_id(project_name: str) -> str:
    safe = project_name.replace("_", "-").replace(" ", "-").lower()
    return f"cap-{safe}"


def get_container_name(project_name: str) -> str:
    return get_project_id(project_name)


def resolve_project_path(given_path: str | None = None) -> str:
    if given_path:
        return str(Path(given_path).resolve())
    current = Path(os.getcwd()).resolve()
    for parent in [current] + list(current.parents):
        if (parent / WORKBENCH_DIR / CONFIG_FILE).exists():
            return str(parent)
    raise FileNotFoundError(
        "No .workbench/project.yaml found in current or parent directories. Run from a project directory or use --path."
    )
