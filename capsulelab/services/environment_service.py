from pathlib import Path

import yaml

from capsulelab.services import project_service

DEPENDENCY_FILE = "requirements.txt"


def _dependency_path(project_path: str) -> Path:
    return Path(project_path) / DEPENDENCY_FILE


def _config_path(project_path: str) -> Path:
    return Path(project_path) / project_service.WORKBENCH_DIR / project_service.CONFIG_FILE


def _read_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    dependencies: list[str] = []
    for line in path.read_text().splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            dependencies.append(item)
    return dependencies


def _load_config_data(project_path: str) -> dict:
    path = _config_path(project_path)
    if not path.exists():
        raise FileNotFoundError(f"Project config not found at {path}")
    return yaml.safe_load(path.read_text()) or {}


def _write_config_data(project_path: str, data: dict) -> None:
    _config_path(project_path).write_text(yaml.safe_dump(data, sort_keys=False))


def describe(project_path: str) -> dict:
    config = project_service.load_config(project_path)
    requirements_path = _dependency_path(project_path)
    return {
        "runtime": {
            "type": config.runtime.type.value,
            "dockerfile": config.runtime.dockerfile,
            "image": config.runtime.image,
            "gpu": config.runtime.gpu,
        },
        "dependency_file": DEPENDENCY_FILE,
        "dependency_file_exists": requirements_path.exists(),
        "dependencies": _read_requirements(requirements_path),
        "environment": dict(config.environment),
    }


def add_dependency(project_path: str, dependency: str) -> dict:
    item = dependency.strip()
    if not item or "\n" in item or "\r" in item:
        raise ValueError("Dependency must be a single non-empty line.")
    requirements_path = _dependency_path(project_path)
    existing = _read_requirements(requirements_path)
    if item not in existing:
        prefix = requirements_path.read_text() if requirements_path.exists() else ""
        separator = "" if not prefix or prefix.endswith("\n") else "\n"
        requirements_path.write_text(f"{prefix}{separator}{item}\n")
    return describe(project_path)


def set_environment_variable(project_path: str, name: str, value: str) -> dict:
    key = name.strip()
    if not key or any(ch.isspace() for ch in key) or "=" in key:
        raise ValueError("Environment variable name must be non-empty and contain no whitespace or '='.")
    data = _load_config_data(project_path)
    environment = data.setdefault("environment", {})
    environment[key] = value
    _write_config_data(project_path, data)
    return describe(project_path)


def remove_environment_variable(project_path: str, name: str) -> dict:
    key = name.strip()
    data = _load_config_data(project_path)
    environment = data.setdefault("environment", {})
    environment.pop(key, None)
    _write_config_data(project_path, data)
    return describe(project_path)
