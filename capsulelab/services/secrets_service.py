from __future__ import annotations

from capsulelab.core.checks import DoctorCheck
from capsulelab.core.errors import Severity
from capsulelab.core.project import ProjectConfig
from capsulelab.db.repositories import secrets


def set_secret(project_id: str, name: str, value: str, location: str | None = None):
    secrets.set(project_id, name, value, location)


def remove_secret(project_id: str, name: str, location: str | None = None):
    secrets.remove(project_id, name, location)


def list_secret_presence(project_id: str) -> list[dict]:
    return secrets.list(project_id)


def check_health(project_id: str, config: ProjectConfig) -> list[DoctorCheck]:
    missing = missing_required_secrets(project_id, config)
    return [
        DoctorCheck(
            label="Required secrets",
            severity=Severity.WARNING,
            ok=not bool(missing),
            detail="All present" if not missing else f"Missing: {', '.join(missing)}",
            suggestion="Set with: cap secrets set <name>",
        )
    ]


def missing_required_secrets(project_id: str, config: ProjectConfig, location: str | None = None) -> list[str]:
    missing: list[str] = []
    for secret in config.secrets:
        if secret.location and secret.location != location:
            continue
        if secret.required and not secrets.get(project_id, secret.name, location or secret.location):
            missing.append(secret.name)
    return missing
