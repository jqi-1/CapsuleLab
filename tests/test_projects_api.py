from fastapi import HTTPException

from backend.api import projects
from capsulelab.core.project import ProjectConfig, RuntimeConfig


def test_import_project_endpoint_uses_git_import(monkeypatch):
    calls = {}

    def fake_import(source, dest=None, name=None, scaffold=True):
        calls.update({"source": source, "dest": dest, "name": name, "scaffold": scaffold})
        return {"project_id": "cap-demo", "name": "demo", "path": "/tmp/demo", "detected": {}}

    monkeypatch.setattr(projects.git_service, "import_project", fake_import)

    result = projects.import_project(
        projects.ImportProjectRequest(source="https://example.test/demo.git", path="/tmp/demo", name="demo")
    )

    assert result["project_id"] == "cap-demo"
    assert calls == {
        "source": "https://example.test/demo.git",
        "dest": "/tmp/demo",
        "name": "demo",
        "scaffold": True,
    }


def test_import_project_endpoint_maps_missing_path_to_404(monkeypatch):
    def fake_import(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(projects.git_service, "import_project", fake_import)

    try:
        projects.import_project(projects.ImportProjectRequest(source="/missing"))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_delete_project_removes_existing_inventory_row(monkeypatch):
    removed = []

    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})
    monkeypatch.setattr("capsulelab.db.repositories.projects.remove", lambda project_id: removed.append(project_id))

    result = projects.delete_project("cap-demo")

    assert result == {"status": "removed", "project_id": "cap-demo"}
    assert removed == ["cap-demo"]


def test_delete_project_404s_for_missing_inventory_row(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: None)

    try:
        projects.delete_project("cap-missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_setup_ide_endpoint_uses_project_path(monkeypatch):
    calls = {}

    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_setup(path, ide, project_name=None):
        calls.update({"path": path, "ide": ide, "project_name": project_name})
        return {"ide": ide, "files": [], "instructions": []}

    monkeypatch.setattr(projects.ide_service, "setup_ide", fake_setup)

    result = projects.setup_ide("cap-demo", projects.IdeSetupRequest(ide="cursor"))

    assert result["ide"] == "cursor"
    assert calls == {"path": "/tmp/demo", "ide": "cursor", "project_name": "demo"}


def test_ide_instructions_endpoint_maps_unknown_ide(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_instructions(*args, **kwargs):
        raise ValueError("Unsupported IDE")

    monkeypatch.setattr(projects.ide_service, "attach_instructions", fake_instructions)

    try:
        projects.ide_instructions("cap-demo", "unknown")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")


def test_project_status_returns_full_status(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})
    monkeypatch.setattr(projects.project_service, "load_config", lambda path: ProjectConfig(name="demo", runtime=RuntimeConfig(image="demo:dev")))
    monkeypatch.setattr(projects.project_service, "validate", lambda config, path: [])
    monkeypatch.setattr(projects.docker_service, "check_docker_status", lambda: type("DockerStatus", (), {
        "available": False,
        "binary_found": False,
        "daemon_running": False,
        "socket_accessible": False,
        "version": "",
        "error": "offline",
    })())
    monkeypatch.setattr(projects.gpu_service, "get_gpu_info", lambda: type("GpuInfo", (), {"available": False, "name": "", "vram_mb": 0})())
    monkeypatch.setattr(projects.git_service, "git_status", lambda path: {"is_repo": False, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False})
    monkeypatch.setattr(projects.resource_service, "project_resources", lambda path: {
        "disk": {"path": path, "total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "free_percent": 0},
        "gpu": {"available": False, "gpus": []},
    })
    monkeypatch.setattr(projects.compose_service, "status", lambda path: {"detected": False})
    monkeypatch.setattr("capsulelab.db.repositories.builds.get_metadata", lambda project_id: None)
    monkeypatch.setattr(projects.secrets_service, "list_secret_presence", lambda project_id: [])
    monkeypatch.setattr(projects.secrets_service, "missing_required_secrets", lambda project_id, config: [])

    result = projects.project_status("cap-demo")

    assert result["project_id"] == "cap-demo"
    assert result["name"] == "demo"
    assert "project" in result
    assert "system" in result
    assert result["compose"] == {"detected": False}


def test_project_environment_endpoint_uses_project_path(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})
    monkeypatch.setattr(projects.environment_service, "describe", lambda path: {"path": path, "dependencies": [], "environment": {}})

    result = projects.project_environment("cap-demo")

    assert result["path"] == "/tmp/demo"


def test_add_project_dependency_endpoint_maps_validation_error(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_add(*args, **kwargs):
        raise ValueError("bad dependency")

    monkeypatch.setattr(projects.environment_service, "add_dependency", fake_add)

    try:
        projects.add_project_dependency("cap-demo", projects.AddDependencyRequest(dependency=""))
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")


def test_set_project_environment_variable_endpoint(monkeypatch):
    calls = {}
    monkeypatch.setattr("capsulelab.db.repositories.projects.get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_set(path, name, value):
        calls.update({"path": path, "name": name, "value": value})
        return {"environment": {name: value}}

    monkeypatch.setattr(projects.environment_service, "set_environment_variable", fake_set)

    result = projects.set_project_environment_variable(
        "cap-demo",
        projects.EnvironmentVariableRequest(name="API_URL", value="https://example.test"),
    )

    assert result["environment"] == {"API_URL": "https://example.test"}
    assert calls == {"path": "/tmp/demo", "name": "API_URL", "value": "https://example.test"}
