from backend.db import sqlite
from backend.models.project import ProjectConfig


def set_secret(project_id: str, name: str, value: str, location: str | None = None):
    sqlite.set_secret(project_id, name, value, location)


def remove_secret(project_id: str, name: str, location: str | None = None):
    sqlite.remove_secret(project_id, name, location)


def list_secret_presence(project_id: str) -> list[dict]:
    return sqlite.list_secrets(project_id)


def missing_required_secrets(project_id: str, config: ProjectConfig, location: str | None = None) -> list[str]:
    missing: list[str] = []
    for secret in config.secrets:
        if secret.location and secret.location != location:
            continue
        if secret.required and not sqlite.get_secret(project_id, secret.name, location or secret.location):
            missing.append(secret.name)
    return missing
