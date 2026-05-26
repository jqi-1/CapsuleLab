import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from backend.models.project import ProjectConfig


MAINTAINED_TEMPLATES = ["python-basic", "pytorch-cuda", "streamlit-dashboard", "research-rag", "deployable-fastapi", "opensource-python-package"]
TEMPLATE_PROFILES: dict[str, str] = {
    "python-basic": "research",
    "pytorch-cuda": "research",
    "streamlit-dashboard": "research",
    "research-rag": "research",
    "deployable-fastapi": "deployable",
    "opensource-python-package": "opensource",
}


@dataclass
class TemplateCheck:
    label: str
    ok: bool
    detail: str


def templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "templates"


def load_manifest(base_dir: Path | None = None) -> dict:
    manifest_path = (base_dir or templates_dir()) / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def list_maintained_templates() -> list[str]:
    return MAINTAINED_TEMPLATES.copy()


def list_templates_for_profile(mode: str | None) -> list[str]:
    if mode is None:
        return MAINTAINED_TEMPLATES.copy()
    return [t for t in MAINTAINED_TEMPLATES if TEMPLATE_PROFILES.get(t) == mode]


def list_profile_catalog(base_dir: Path | None = None) -> dict[str, list[str]]:
    profiles: dict[str, list[str]] = {}
    manifest = load_manifest(base_dir)
    for name, meta in manifest.items():
        mode = meta.get("mode", "research")
        profiles.setdefault(mode, []).append(name)
    return profiles


def validate_template(name: str, base_dir: Path | None = None) -> list[TemplateCheck]:
    base = base_dir or templates_dir()
    template_path = base / name
    checks: list[TemplateCheck] = []

    if name not in MAINTAINED_TEMPLATES:
        checks.append(TemplateCheck("Maintained template", False, f"{name} is not in the maintained catalog"))
    else:
        checks.append(TemplateCheck("Maintained template", True, "Listed in maintained catalog"))

    if not template_path.exists():
        checks.append(TemplateCheck("Template directory", False, f"Missing {template_path}"))
        return checks
    checks.append(TemplateCheck("Template directory", True, str(template_path)))

    manifest = load_manifest(base)
    checks.append(
        TemplateCheck(
            "Manifest entry",
            name in manifest,
            "Found" if name in manifest else "Missing from templates/manifest.json",
        )
    )

    dockerfile = template_path / "Dockerfile"
    checks.append(TemplateCheck("Dockerfile", dockerfile.exists(), "Found" if dockerfile.exists() else "Missing"))
    if dockerfile.exists():
        dockerfile_text = dockerfile.read_text().strip()
        checks.append(TemplateCheck("Dockerfile base image", dockerfile_text.startswith("FROM "), "Starts with FROM" if dockerfile_text.startswith("FROM ") else "Missing FROM"))
        checks.append(TemplateCheck("Dockerfile workdir", "WORKDIR" in dockerfile_text, "Found" if "WORKDIR" in dockerfile_text else "Missing WORKDIR"))
        checks.append(TemplateCheck("Dockerfile command", "CMD" in dockerfile_text, "Found" if "CMD" in dockerfile_text else "Missing CMD"))

    config_path = template_path / ".workbench" / "project.yaml"
    config = None
    checks.append(TemplateCheck("Project config", config_path.exists(), "Found" if config_path.exists() else "Missing .workbench/project.yaml"))
    if config_path.exists():
        try:
            config = ProjectConfig(**yaml.safe_load(config_path.read_text()))
            checks.append(TemplateCheck("Project config schema", True, f"Project: {config.name}"))
        except (ValidationError, yaml.YAMLError, TypeError) as e:
            checks.append(TemplateCheck("Project config schema", False, str(e)))

    readme = template_path / "README.md"
    checks.append(TemplateCheck("README", readme.exists() and bool(readme.read_text().strip()) if readme.exists() else False, "Found" if readme.exists() else "Missing"))

    requirements = template_path / "requirements.txt"
    checks.append(TemplateCheck("Requirements", requirements.exists() and bool(requirements.read_text().strip()) if requirements.exists() else False, "Found" if requirements.exists() else "Missing"))

    starter_files = list((template_path / "notebooks").glob("*.ipynb")) if (template_path / "notebooks").exists() else []
    if (template_path / "app.py").exists():
        starter_files.append(template_path / "app.py")
    checks.append(
        TemplateCheck(
            "Starter notebook or app",
            bool(starter_files),
            ", ".join(str(p.relative_to(template_path)) for p in starter_files) if starter_files else "Missing starter notebook or app",
        )
    )

    if config:
        if config.apps:
            for app in config.apps:
                port_ok = app.port is None or 1 <= app.port <= 65535
                ok = bool(app.id and app.command and port_ok)
                detail = f"{app.id}: {app.command} on {app.port or 'no port'}" if ok else f"Invalid app entry: {app.model_dump()}"
                checks.append(TemplateCheck(f"App command {app.id}", ok, detail))
        else:
            checks.append(TemplateCheck("App commands", False, "No apps configured"))

    return checks


def validate_catalog(base_dir: Path | None = None) -> dict[str, list[TemplateCheck]]:
    return {name: validate_template(name, base_dir) for name in MAINTAINED_TEMPLATES}
