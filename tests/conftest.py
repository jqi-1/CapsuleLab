import pytest
import shutil
import subprocess


def docker_daemon_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def pytest_collection_modifyitems(config, items):
    docker_ok = docker_daemon_available()
    for item in items:
        if "docker" in item.keywords and not docker_ok:
            skip_docker = pytest.mark.skip(reason="Docker daemon not available")
            item.add_marker(skip_docker)
        if "ssh" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="SSH tests require a configured remote host"))
        if "compose" in item.keywords:
            if not shutil.which("docker-compose") and not shutil.which("docker"):
                item.add_marker(pytest.mark.skip(reason="Docker Compose not available"))
