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
