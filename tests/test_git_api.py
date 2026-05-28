from fastapi import HTTPException

from backend.api import backlog


def test_git_commit_endpoint_uses_project_path(monkeypatch):
    calls = {}

    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    def fake_commit(path, message, all_changes=True):
        calls.update({"path": path, "message": message, "all_changes": all_changes})
        return {"status": "committed", "commit": "abc123"}

    monkeypatch.setattr(backlog.git_service, "commit", fake_commit)

    result = backlog.git_commit("cap-demo", backlog.GitCommitRequest(message="save work", all_changes=False))

    assert result["status"] == "committed"
    assert calls == {"path": "/tmp/demo", "message": "save work", "all_changes": False}


def test_git_init_endpoint_uses_project_path(monkeypatch):
    calls = {}

    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    def fake_init_repo(path):
        calls["path"] = path
        return {"status": "initialized", "path": path, "commit": "abc123"}

    monkeypatch.setattr(backlog.git_service, "init_repo", fake_init_repo)

    result = backlog.git_init("cap-demo")

    assert result["status"] == "initialized"
    assert calls == {"path": "/tmp/demo"}


def test_git_publish_endpoint_maps_git_errors(monkeypatch):
    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    def fake_publish(*args, **kwargs):
        raise backlog.git_service.GitError("bad remote")

    monkeypatch.setattr(backlog.git_service, "publish", fake_publish)

    try:
        backlog.git_publish("cap-demo", backlog.GitPublishRequest(remote_url="bad"))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail["error_code"] == "git_error"
    else:
        raise AssertionError("Expected HTTPException")


def test_git_branch_endpoint_switches_branch(monkeypatch):
    calls = {}

    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    def fake_switch(path, branch, create=False):
        calls.update({"path": path, "branch": branch, "create": create})
        return {"status": "switched", "branch": branch}

    monkeypatch.setattr(backlog.git_service, "switch_branch", fake_switch)

    result = backlog.git_switch_branch("cap-demo", backlog.GitBranchRequest(branch="feature", create=True))

    assert result == {"status": "switched", "branch": "feature"}
    assert calls == {"path": "/tmp/demo", "branch": "feature", "create": True}


def test_graph_index_endpoint_returns_full_graph(monkeypatch):
    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    class FakeGraph:
        project_id = "cap-demo"
        project_path = "/tmp/demo"
        nodes = []
        edges = []
        summary = {"node_count": 0, "edge_count": 0}

    monkeypatch.setattr(backlog.graph_service, "index_project", lambda project_id, path: FakeGraph())
    monkeypatch.setattr(
        backlog.graph_service,
        "to_dict",
        lambda graph: {
            "project_id": graph.project_id,
            "project_path": graph.project_path,
            "nodes": graph.nodes,
            "edges": graph.edges,
            "summary": graph.summary,
        },
    )

    result = backlog.index_project_graph("cap-demo")

    assert result["project_id"] == "cap-demo"
    assert result["summary"] == {"node_count": 0, "edge_count": 0}


def test_graph_search_endpoint_uses_query_params(monkeypatch):
    calls = {}
    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))

    def fake_search(project_id, path, query="", kind=None, limit=25):
        calls.update({"project_id": project_id, "path": path, "query": query, "kind": kind, "limit": limit})
        return {"nodes": [], "edges": [], "summary": {}}

    monkeypatch.setattr(backlog.graph_service, "search", fake_search)

    result = backlog.search_project_graph("cap-demo", q="service", kind="function", limit=3)

    assert result["nodes"] == []
    assert calls == {"project_id": "cap-demo", "path": "/tmp/demo", "query": "service", "kind": "function", "limit": 3}


def test_graph_inspect_endpoint_maps_missing_node(monkeypatch):
    monkeypatch.setattr(backlog, "_project", lambda project_id: ({"path": "/tmp/demo"}, object()))
    monkeypatch.setattr(
        backlog.graph_service, "inspect_node", lambda *args, **kwargs: (_ for _ in ()).throw(KeyError("missing"))
    )

    try:
        backlog.inspect_project_graph_node("cap-demo", "missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_agent_action_endpoints_round_trip(monkeypatch):
    from capsulelab.services import agent_service

    monkeypatch.setattr(
        backlog.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"}
    )
    monkeypatch.setattr(backlog.project_service, "load_config", lambda path: object())
    actions = []

    def fake_propose(project_id, action_type, title, rationale, files=None):
        action = agent_service.AgentAction(
            id="action-1",
            project_id=project_id,
            action_type=action_type,
            title=title,
            rationale=rationale,
            files=files or [],
        )
        actions.append(action)
        return action

    def fake_list(project_id):
        return actions

    def fake_review(project_id, action_id, approved, reviewer="", note=""):
        actions[0].status = "approved" if approved else "rejected"
        actions[0].reviewer = reviewer
        actions[0].review_note = note
        return actions[0]

    monkeypatch.setattr(agent_service, "propose_action", fake_propose)
    monkeypatch.setattr(agent_service, "list_actions", fake_list)
    monkeypatch.setattr(agent_service, "review_action", fake_review)

    proposed = backlog.propose_agent_action(
        "cap-demo",
        backlog.AgentActionRequest(
            action_type="docs_update",
            title="Update README",
            rationale="Keep setup current",
            files=["README.md"],
        ),
    )
    listed = backlog.list_agent_actions("cap-demo")
    reviewed = backlog.review_agent_action(
        "cap-demo",
        "action-1",
        backlog.AgentActionReviewRequest(approved=True, reviewer="tester", note="ok"),
    )

    assert proposed["id"] == "action-1"
    assert listed[0]["title"] == "Update README"
    assert reviewed["status"] == "approved"
    assert reviewed["reviewer"] == "tester"
