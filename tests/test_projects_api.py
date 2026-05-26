from fastapi import HTTPException

from backend.api import projects


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

    monkeypatch.setattr(projects, "get_project", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})
    monkeypatch.setattr(projects, "remove_project", lambda project_id: removed.append(project_id))

    result = projects.delete_project("cap-demo")

    assert result == {"status": "removed", "project_id": "cap-demo"}
    assert removed == ["cap-demo"]


def test_delete_project_404s_for_missing_inventory_row(monkeypatch):
    monkeypatch.setattr(projects, "get_project", lambda project_id: None)

    try:
        projects.delete_project("cap-missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_setup_ide_endpoint_uses_project_path(monkeypatch):
    calls = {}

    monkeypatch.setattr(projects, "get_project", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_setup(path, ide, project_name=None):
        calls.update({"path": path, "ide": ide, "project_name": project_name})
        return {"ide": ide, "files": [], "instructions": []}

    monkeypatch.setattr(projects.ide_service, "setup_ide", fake_setup)

    result = projects.setup_ide("cap-demo", projects.IdeSetupRequest(ide="cursor"))

    assert result["ide"] == "cursor"
    assert calls == {"path": "/tmp/demo", "ide": "cursor", "project_name": "demo"}


def test_ide_instructions_endpoint_maps_unknown_ide(monkeypatch):
    monkeypatch.setattr(projects, "get_project", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_instructions(*args, **kwargs):
        raise ValueError("Unsupported IDE")

    monkeypatch.setattr(projects.ide_service, "attach_instructions", fake_instructions)

    try:
        projects.ide_instructions("cap-demo", "unknown")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")
