import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capsulelab.core.document_store import DocumentStore

REGISTRY_CREDENTIALS = DocumentStore(Path.home() / ".capsulelab" / "registry_credentials", default={})


@dataclass
class RegistryInfo:
    name: str
    host: str
    url: str
    description: str
    login_command: str
    image_template: str
    credential_hint: str
    requires_token: bool = False


REGISTRIES: dict[str, RegistryInfo] = {
    "dockerhub": RegistryInfo(
        name="Docker Hub",
        host="docker.io",
        url="https://hub.docker.com",
        description="Public container image registry by Docker",
        login_command="docker login",
        image_template="{namespace}/{repository}:{tag}",
        credential_hint="Use a Docker Hub username and password or access token.",
        requires_token=False,
    ),
    "ghcr": RegistryInfo(
        name="GitHub Container Registry",
        host="ghcr.io",
        url="https://ghcr.io",
        description="Container registry integrated with GitHub packages",
        login_command="docker login ghcr.io",
        image_template="ghcr.io/{namespace}/{repository}:{tag}",
        credential_hint="Use your GitHub username and a personal access token with package permissions.",
        requires_token=True,
    ),
    "gitlab": RegistryInfo(
        name="GitLab Container Registry",
        host="registry.gitlab.com",
        url="https://gitlab.com/users/sign_in",
        description="Container registry integrated with GitLab",
        login_command="docker login registry.gitlab.com",
        image_template="registry.gitlab.com/{namespace}/{repository}:{tag}",
        credential_hint="Use your GitLab username and a personal, project, or deploy token with registry permissions.",
        requires_token=True,
    ),
    "ngc": RegistryInfo(
        name="NVIDIA NGC",
        host="nvcr.io",
        url="https://catalog.ngc.nvidia.com",
        description="NVIDIA GPU-optimized container registry",
        login_command="docker login nvcr.io",
        image_template="nvcr.io/{namespace}/{repository}:{tag}",
        credential_hint="Use '$oauthtoken' as the username and an NGC API key as the password.",
        requires_token=True,
    ),
    "huggingface": RegistryInfo(
        name="Hugging Face",
        host="registry.hf.space",
        url="https://huggingface.co",
        description="Hugging Face model and container registry",
        login_command="docker login registry.hf.space",
        image_template="registry.hf.space/{namespace}-{repository}:{tag}",
        credential_hint="Use your Hugging Face username and a token with write access.",
        requires_token=True,
    ),
}


def list_registries() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "name": r.name,
            "host": r.host,
            "url": r.url,
            "description": r.description,
            "login_command": r.login_command,
            "image_template": r.image_template,
            "credential_hint": r.credential_hint,
            "requires_token": r.requires_token,
            "logged_in": _is_logged_in(r.login_command),
        }
        for key, r in REGISTRIES.items()
    }


def publish_plan(
    registry_key: str,
    source_image: str,
    namespace: str,
    repository: str,
    tag: str = "latest",
) -> dict:
    reg = REGISTRIES.get(registry_key)
    if not reg:
        raise ValueError(f"Unknown registry '{registry_key}'. Available: {', '.join(REGISTRIES.keys())}")
    if not source_image:
        raise ValueError("source_image is required")
    if not namespace:
        raise ValueError("namespace is required")
    if not repository:
        raise ValueError("repository is required")
    target_image = reg.image_template.format(namespace=namespace.strip("/"), repository=repository.strip("/"), tag=tag)
    commands = [
        reg.login_command,
        f"docker tag {source_image} {target_image}",
        f"docker push {target_image}",
    ]
    return {
        "registry": registry_key,
        "name": reg.name,
        "host": reg.host,
        "url": reg.url,
        "requires_token": reg.requires_token,
        "credential_hint": reg.credential_hint,
        "source_image": source_image,
        "target_image": target_image,
        "commands": commands,
        "notes": [
            "Review the target image name before tagging.",
            "Do not paste tokens into project files or shell history.",
            "Use 'cap registry login' to authenticate, then tag and push.",
        ],
    }


def login(registry_key: str, username: str, password: str) -> dict:
    reg = REGISTRIES.get(registry_key)
    if not reg:
        raise ValueError(f"Unknown registry '{registry_key}'. Available: {', '.join(REGISTRIES.keys())}")
    cmd = reg.login_command.split() + ["--username", username, "--password-stdin"]
    try:
        proc = subprocess.run(
            cmd,
            input=password.encode(),
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode().strip()
            return {"ok": False, "error": stderr, "registry": registry_key}
        _save_credential(registry_key, username)
        return {"ok": True, "registry": registry_key, "username": username}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Login timed out", "registry": registry_key}
    except FileNotFoundError:
        return {"ok": False, "error": "Docker not found", "registry": registry_key}


def logout(registry_key: str) -> dict:
    reg = REGISTRIES.get(registry_key)
    if not reg:
        raise ValueError(f"Unknown registry '{registry_key}'")
    cmd = reg.login_command.split()
    logout_cmd = ["docker", "logout"] + (cmd[2:] if len(cmd) > 2 else [])
    try:
        subprocess.run(logout_cmd, capture_output=True, timeout=15)
        _remove_credential(registry_key)
        return {"ok": True, "registry": registry_key}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Logout timed out", "registry": registry_key}


def push_image(image_tag: str, registry_key: str | None = None) -> dict:
    if registry_key:
        reg = REGISTRIES.get(registry_key)
        if not reg:
            raise ValueError(f"Unknown registry '{registry_key}'")
    try:
        result = subprocess.run(
            ["docker", "push", image_tag],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip(), "image": image_tag}
        return {"ok": True, "image": image_tag, "output": result.stdout.strip()[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Push timed out", "image": image_tag}
    except FileNotFoundError:
        return {"ok": False, "error": "Docker not found", "image": image_tag}


def pull_image(image_tag: str) -> dict:
    try:
        result = subprocess.run(
            ["docker", "pull", image_tag],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip(), "image": image_tag}
        return {"ok": True, "image": image_tag, "output": result.stdout.strip()[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Pull timed out", "image": image_tag}
    except FileNotFoundError:
        return {"ok": False, "error": "Docker not found", "image": image_tag}


def tag_image(source_tag: str, target_tag: str) -> dict:
    try:
        result = subprocess.run(
            ["docker", "tag", source_tag, target_tag],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip(), "source": source_tag, "target": target_tag}
        return {"ok": True, "source": source_tag, "target": target_tag}
    except FileNotFoundError:
        return {"ok": False, "error": "Docker not found"}


def _is_logged_in(login_cmd: str) -> bool:
    parts = login_cmd.split()
    registry = parts[2] if len(parts) > 2 else "index.docker.io"
    try:
        result = subprocess.run(
            ["docker", "login", registry, "--help"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _save_credential(registry_key: str, username: str):
    REGISTRY_CREDENTIALS.update({registry_key: {"username": username}})


def _remove_credential(registry_key: str):
    REGISTRY_CREDENTIALS.update(lambda creds: {k: v for k, v in creds.items() if k != registry_key})


def credential_status() -> dict:
    return REGISTRY_CREDENTIALS.read()
