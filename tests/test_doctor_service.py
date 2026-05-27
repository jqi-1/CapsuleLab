import yaml

from capsulelab.services import doctor_service
from capsulelab.services.docker_service import DockerStatus
from capsulelab.services.gpu_service import GpuInfo


def _write_project(path, config=None):
    (path / ".workbench").mkdir()
    data = config or {
        "name": "demo",
        "runtime": {"type": "docker", "dockerfile": "Dockerfile", "image": "demo:dev"},
        "mounts": [{"source": ".", "target": "/workspace"}],
        "apps": [
            {
                "name": "JupyterLab",
                "id": "jupyter",
                "command": "jupyter lab --ip=0.0.0.0 --port=8888",
                "port": 8888,
            }
        ],
    }
    (path / ".workbench" / "project.yaml").write_text(yaml.safe_dump(data))
    (path / "Dockerfile").write_text("FROM python:3.12-slim\nWORKDIR /workspace\nRUN pip install jupyterlab\n")
    (path / "README.md").write_text("Demo\n\nRun cap doctor, cap build, cap start, and cap app start jupyter.\n")
    (path / "requirements.txt").write_text("jupyterlab==4.2.0\n")


def _stub_external_checks(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.list", lambda: [])
    monkeypatch.setattr("capsulelab.db.repositories.builds.get_metadata", lambda project_id: None)
    monkeypatch.setattr(
        doctor_service.docker_service,
        "check_docker_status",
        lambda: DockerStatus(True, True, True, True, version="25.0.0"),
    )
    monkeypatch.setattr(doctor_service.gpu_service, "get_gpu_info", lambda: GpuInfo(False))
    monkeypatch.setattr(doctor_service.gpu_service, "docker_gpu_available", lambda: False)
    monkeypatch.setattr(doctor_service.secrets_service, "missing_required_secrets", lambda project_id, config: [])
    monkeypatch.setattr(
        doctor_service.git_service,
        "git_status",
        lambda path: {
            "is_repo": True,
            "branch": "main",
            "remote": "origin",
            "dirty_files": 0,
            "lfs_available": True,
        },
    )
    monkeypatch.setattr(
        doctor_service.compose_service,
        "status",
        lambda path: {
            "available": False,
            "binary": "",
            "compose_file": None,
            "detected": False,
            "services": [],
            "error": "",
        },
    )


def test_project_doctor_for_path_returns_structured_reproducibility_checks(tmp_path, monkeypatch):
    _write_project(tmp_path)
    _stub_external_checks(monkeypatch)

    report = doctor_service.project_doctor_for_path(str(tmp_path))
    labels = {check.label: check for check in report.checks}

    assert report.project_name == "demo"
    assert labels["Package manifest"].ok is True
    assert labels["Dockerfile"].ok is True
    assert labels["App 'jupyter': command"].ok is True
    assert labels["Git: clean working tree"].ok is True
    assert labels["Writable output 'outputs'"].ok is True
    assert not (tmp_path / "outputs").exists()


def test_project_doctor_reports_compose_runtime_without_compose_file(tmp_path, monkeypatch):
    _write_project(
        tmp_path,
        {
            "name": "stack",
            "runtime": {"type": "compose", "dockerfile": "Dockerfile", "image": "stack:dev"},
        },
    )
    _stub_external_checks(monkeypatch)

    report = doctor_service.project_doctor_for_path(str(tmp_path))
    compose_check = next(check for check in report.checks if check.label == "Compose file")

    assert compose_check.ok is False
    assert compose_check.severity.value == "error"
