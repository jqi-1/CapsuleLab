from capsulelab.db.repositories import secrets
from capsulelab.core.project import ProjectConfig


def set_secret(project_id: str, name: str, value: str, location: str | None = None):
    secrets.set(project_id, name, value, location)


def remove_secret(project_id: str, name: str, location: str | None = None):
    secrets.remove(project_id, name, location)


def list_secret_presence(project_id: str) -> list[dict]:
    return secrets.list(project_id)


def missing_required_secrets(project_id: str, config: ProjectConfig, location: str | None = None) -> list[str]:
    missing: list[str] = []
    for secret in config.secrets:
        if secret.location and secret.location != location:
            continue
        if secret.required and not secrets.get(project_id, secret.name, location or secret.location):
            missing.append(secret.name)
    return missing
