import pytest
from backend.services import docker_service


def test_docker_available():
    result = docker_service.check_docker()
    assert isinstance(result, bool)


def test_ps_returns_list():
    containers = docker_service.ps()
    assert isinstance(containers, list)
