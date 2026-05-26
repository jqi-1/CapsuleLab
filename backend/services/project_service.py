import os
import shutil
import yaml
from pathlib import Path
from backend.models.project import ProjectConfig, default_presets, ProjectMode


WORKBENCH_DIR = ".workbench"
CONFIG_FILE = "project.yaml"


def load_config(project_path: str) -> ProjectConfig:
    config_path = Path(project_path) / WORKBENCH_DIR / CONFIG_FILE
    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found at {config_path}")
    with open(config_path) as f:
        data = yaml.safe_load(f)
    if not data:
        raise ValueError(f"Empty or invalid YAML in {config_path}")
    cfg = ProjectConfig(**data)
    if cfg.mode and not cfg.presets:
        cfg.presets = default_presets(cfg.mode)
    return cfg


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
            warnings.append(f"Deployable mode: tests/ directory not found")
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
            warnings.append(f"Research mode: notebooks/ directory not found")

    return warnings


def create_from_template(name: str, template_path: str, dest_path: str, image_name: str | None = None) -> str:
    dest = Path(dest_path)
    if dest.exists():
        raise FileExistsError(f"Destination {dest_path} already exists")
    src = Path(template_path)
    if not src.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    shutil.copytree(src, dest)
    config_path = dest / WORKBENCH_DIR / CONFIG_FILE
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["name"] = name
        if image_name:
            config["runtime"]["image"] = image_name
        elif "image" in config.get("runtime", {}):
            config["runtime"]["image"] = f"{name}:dev"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    return str(dest)


def find_projects(base_dir: str | None = None) -> list[dict]:
    if base_dir is None:
        base_dir = os.getcwd()
    projects = []
    base = Path(base_dir)
    for child in base.iterdir():
        if child.is_dir():
            config_file = child / WORKBENCH_DIR / CONFIG_FILE
            if config_file.exists():
                try:
                    cfg = load_config(str(child))
                    projects.append({
                        "name": cfg.name,
                        "path": str(child),
                        "config": cfg,
                    })
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
        "No .workbench/project.yaml found in current or parent directories."
        " Run from a project directory or use --path."
    )
