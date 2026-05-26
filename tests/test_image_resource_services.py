from backend.services import image_service, resource_service
import subprocess


def test_image_catalog_has_python():
    catalog = image_service.catalog()

    assert "python" in catalog
    assert catalog["python"]["image"]


def test_byoc_checks_missing_dockerfile(tmp_path):
    checks = image_service.byoc_checks(str(tmp_path))

    assert checks[0]["ok"] is False


def test_disk_status(tmp_path):
    status = resource_service.disk_status(str(tmp_path))

    assert status["free_bytes"] > 0
    assert status["path"] == str(tmp_path.resolve())


def test_gpu_status_handles_non_numeric_metrics(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "NVIDIA GPU, [N/A], [N/A], 8192\n", "")

    monkeypatch.setattr(resource_service.subprocess, "run", fake_run)

    status = resource_service.gpu_status()

    assert status["available"] is True
    assert status["gpus"][0]["utilization_percent"] == 0
