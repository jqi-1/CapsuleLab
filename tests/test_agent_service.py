import json

from capsulelab.core.errors import Severity
from capsulelab.services import agent_service, graph_service


class FakeCheck:
    def __init__(self, label, ok, severity=Severity.WARNING, detail="", suggestion=""):
        self.label = label
        self.ok = ok
        self.severity = severity
        self.detail = detail
        self.suggestion = suggestion


class FakeReport:
    checks = [
        FakeCheck("README", True, Severity.INFO, "Found"),
        FakeCheck("Dockerfile", False, Severity.ERROR, "Missing", "Add Dockerfile"),
    ]


def test_build_project_context_writes_json_and_agent_summary(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".workbench").mkdir()
    (project / ".workbench" / "project.yaml").write_text(
        "name: demo\n"
        "runtime:\n"
        "  image: demo:dev\n"
        "datasets:\n"
        "  - name: sample\n"
        "    path: data\n"
        "    target: /data\n"
        "secrets:\n"
        "  - name: API_KEY\n"
        "apps:\n"
        "  - name: Jupyter\n"
        "    id: jupyter\n"
        "    command: jupyter lab\n"
        "    port: 8888\n"
    )
    (project / "main.py").write_text("def run():\n    return 1\n")
    monkeypatch.setattr(agent_service, "AGENT_STORAGE", tmp_path / "agent")
    monkeypatch.setattr(graph_service, "GRAPH_STORAGE", tmp_path / "graphs")
    agent_service.AGENT_STORAGE.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        agent_service.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": str(project)}
    )
    monkeypatch.setattr(
        agent_service.runs, "list", lambda project_id: [{"id": "run-1", "name": "baseline", "status": "finished"}]
    )
    monkeypatch.setattr(agent_service.doctor_service, "project_doctor_for_path", lambda *args, **kwargs: FakeReport())

    agent_service.build_project_context("cap-demo")
    saved = json.loads((tmp_path / "agent" / "cap-demo.json").read_text())
    loaded = agent_service.get_context("cap-demo")

    assert saved["context"]["project_id"] == "cap-demo"
    assert loaded is not None
    assert loaded.summary.startswith("demo is a CapsuleLab project")
    assert loaded.known_issues[0]["label"] == "Dockerfile"
    assert loaded.app_list[0]["id"] == "jupyter"
    assert loaded.data_mounts[1]["kind"] == "dataset"
    assert loaded.secret_refs[0]["name"] == "API_KEY"
    assert loaded.recent_runs == [{"id": "run-1", "name": "baseline", "status": "finished"}]


def test_agent_actions_require_project_boundary(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(agent_service, "AGENT_STORAGE", tmp_path / "agent")
    agent_service.AGENT_STORAGE.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        agent_service.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": str(project)}
    )

    action = agent_service.propose_action(
        "cap-demo",
        "docs_update",
        "Update README",
        "Keep setup instructions current",
        ["README.md"],
    )
    reviewed = agent_service.review_action("cap-demo", action.id, approved=True, reviewer="tester", note="Looks good")

    assert reviewed.status == "approved"
    assert reviewed.files == ["README.md"]
    assert agent_service.list_actions("cap-demo")[0].review_note == "Looks good"

    try:
        agent_service.propose_action("cap-demo", "unsafe", "Escape", "bad", ["../outside.txt"])
    except ValueError as exc:
        assert "escapes project boundary" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
