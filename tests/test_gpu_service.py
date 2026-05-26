import pytest
from backend.services import gpu_service


@pytest.mark.docker
def test_docker_gpu_available_returns_bool():
    result = gpu_service.docker_gpu_available()
    assert isinstance(result, bool)


def test_gpu_info_structure():
    info = gpu_service.get_gpu_info()
    assert hasattr(info, "available")
    assert hasattr(info, "name")
    assert hasattr(info, "vram_mb")
    assert isinstance(info.vram_mb, int)
