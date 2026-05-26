import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REGISTRY_CREDENTIALS = Path.home() / ".capsulelab" / "registry_credentials"


@dataclass
class RegistryInfo:
    name: str
    url: str
    description: str
    login_command: str
    requires_token: bool = False


REGISTRIES: dict[str, RegistryInfo] = {
    "dockerhub": RegistryInfo(
        name="Docker Hub",
        url="https://hub.docker.com",
        description="Public container image registry by Docker",
        login_command="docker login",
        requires_token=False,
    ),
    "ghcr": RegistryInfo(
        name="GitHub Container Registry",
        url="https://ghcr.io",
        description="Container registry integrated with GitHub packages",
        login_command="docker login ghcr.io",
        requires_token=True,
    ),
    "gitlab": RegistryInfo(
        name="GitLab Container Registry",
        url="https://gitlab.com/users/sign_in",
        description="Container registry integrated with GitLab",
        login_command="docker login registry.gitlab.com",
        requires_token=True,
    ),
    "ngc": RegistryInfo(
        name="NVIDIA NGC",
        url="https://catalog.ngc.nvidia.com",
        description="NVIDIA GPU-optimized container registry",
        login_command="docker login nvcr.io",
        requires_token=True,
    ),
    "huggingface": RegistryInfo(
        name="Hugging Face",
        url="https://huggingface.co",
        description="Hugging Face model and container registry",
        login_command="docker login registry.us-west-1.console.aws.amazon.com",  # placeholder
        requires_token=True,
    ),
}


def list_registries() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "name": r.name,
            "url": r.url,
            "description": r.description,
            "login_command": r.login_command,
            "requires_token": r.requires_token,
            "logged_in": _is_logged_in(r.login_command),
        }
        for key, r in REGISTRIES.items()
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
            capture_output=True, text=True, timeout=300,
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
            capture_output=True, text=True, timeout=300,
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
            capture_output=True, text=True, timeout=30,
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
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _save_credential(registry_key: str, username: str):
    REGISTRY_CREDENTIALS.mkdir(parents=True, exist_ok=True)
    creds = {}
    if REGISTRY_CREDENTIALS.exists():
        import json
        try:
            creds = json.loads(REGISTRY_CREDENTIALS.read_text())
        except Exception:
            pass
    creds[registry_key] = {"username": username}
    import json
    REGISTRY_CREDENTIALS.write_text(json.dumps(creds, indent=2))


def _remove_credential(registry_key: str):
    if REGISTRY_CREDENTIALS.exists():
        import json
        try:
            creds = json.loads(REGISTRY_CREDENTIALS.read_text())
            creds.pop(registry_key, None)
            REGISTRY_CREDENTIALS.write_text(json.dumps(creds, indent=2))
        except Exception:
            pass


def credential_status() -> dict:
    if not REGISTRY_CREDENTIALS.exists():
        return {}
    import json
    try:
        return json.loads(REGISTRY_CREDENTIALS.read_text())
    except Exception:
        return {}
