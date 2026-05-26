import pytest
from backend.services import docker_service
from backend.services.docker_service import parse_image_tag, app_log_path, DockerStatus


def test_docker_available():
    result = docker_service.check_docker()
    assert isinstance(result, bool)


@pytest.mark.docker
def test_ps_returns_list():
    containers = docker_service.ps()
    assert isinstance(containers, list)


def test_parse_image_tag_with_tag():
    name, tag = parse_image_tag("myimage:latest")
    assert name == "myimage"
    assert tag == "latest"


def test_parse_image_tag_without_tag():
    name, tag = parse_image_tag("myimage")
    assert name == "myimage"
    assert tag == "dev"


def test_parse_image_tag_multi_colon():
    name, tag = parse_image_tag("registry.io/myimage:v1.0")
    assert name == "registry.io/myimage"
    assert tag == "v1.0"


def test_parse_image_tag_custom_default():
    name, tag = parse_image_tag("myimage", default_tag="prod")
    assert name == "myimage"
    assert tag == "prod"


def test_app_log_path():
    path = app_log_path("jupyter")
    assert path == "/tmp/cap-jupyter.log"


def test_app_log_path_special_chars():
    path = app_log_path("my-app_123")
    assert path == "/tmp/cap-my-app_123.log"


def test_check_docker_status_structure():
    status = docker_service.check_docker_status()
    assert isinstance(status, DockerStatus)
    assert isinstance(status.available, bool)
    assert isinstance(status.binary_found, bool)
    assert isinstance(status.daemon_running, bool)
    assert isinstance(status.socket_accessible, bool)
    assert isinstance(status.error, str)


def test_check_docker_status_version_when_available():
    status = docker_service.check_docker_status()
    if status.available:
        assert len(status.version) > 0
    else:
        assert len(status.error) > 0
