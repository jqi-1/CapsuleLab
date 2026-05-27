from pathlib import Path
import yaml

from capsulelab.services import git_service


def test_ensure_config_scaffolds_project_yaml(tmp_path):
    config_path = git_service.ensure_config(str(tmp_path), "demo")

    assert Path(config_path).exists()
    assert "name: demo" in Path(config_path).read_text()


def test_git_status_non_repo(tmp_path):
    status = git_service.git_status(str(tmp_path))

    assert status["is_repo"] is False


def test_git_status_uses_rev_parse_not_dot_git(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        if args[:2] == ["git", "rev-parse"] and args[2] == "--is-inside-work-tree":
            return "true"
        if args[:2] == ["git", "branch"]:
            return "main"
        if args[:2] == ["git", "remote"]:
            return ""
        if args[:2] == ["git", "status"]:
            return " M file.py\n"
        if args[:2] == ["git", "lfs"]:
            raise git_service.GitError("missing")
        raise AssertionError(args)

    monkeypatch.setattr(git_service, "_run", fake_run)

    status = git_service.git_status(str(tmp_path))

    assert status["is_repo"] is True
    assert status["dirty_files"] == 1
    assert ["git", "rev-parse", "--is-inside-work-tree"] in calls


def test_init_repo_sets_identity_and_commits(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        if args == ["git", "config", "user.name"]:
            raise git_service.GitError("unset")
        if args == ["git", "config", "user.email"]:
            raise git_service.GitError("unset")
        if args == ["git", "status", "--porcelain"]:
            return "A  .workbench/project.yaml"
        if args == ["git", "rev-parse", "--short", "HEAD"]:
            return "abc123"
        return ""

    monkeypatch.setattr(git_service, "_run", fake_run)

    result = git_service.init_repo(str(tmp_path))

    assert result["status"] == "initialized"
    assert result["commit"] == "abc123"
    assert ["git", "config", "user.name", "CapsuleLab"] in calls
    assert ["git", "config", "user.email", "capsulelab@local"] in calls
    assert ["git", "commit", "-m", "Initial commit"] in calls


def test_analyze_project_detects_compose_apps_gpu_and_inputs(tmp_path):
    (tmp_path / "compose.yaml").write_text("services:\n  app:\n    image: demo\n")
    (tmp_path / "Dockerfile").write_text("FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime\n")
    (tmp_path / "requirements.txt").write_text("streamlit==1.40.0\njupyterlab==4.2.0\ntensorboard==2.17.0\n")
    (tmp_path / "app.py").write_text("import streamlit as st\n")
    (tmp_path / "notebooks").mkdir()
    (tmp_path / "notebooks" / "demo.ipynb").write_text("{}")
    (tmp_path / "data").mkdir()

    analysis = git_service.analyze_project(str(tmp_path), name="demo")

    assert analysis["runtime"]["type"] == "compose"
    assert analysis["runtime"]["gpu"] is True
    assert analysis["detected"]["compose_file"] == "compose.yaml"
    assert analysis["detected"]["package_files"] == ["requirements.txt"]
    assert set(analysis["detected"]["app_ids"]) == {"streamlit", "tensorboard", "jupyter"}
    assert {"source": "./data", "target": "/workspace/data", "read_only": True} in analysis["mounts"]


def test_ensure_config_writes_detected_project_yaml(tmp_path):
    (tmp_path / "requirements.txt").write_text("gradio==5.0.0\ntorch==2.4.0\n")
    (tmp_path / "gradio_app.py").write_text("import gradio as gr\n")

    config_path = Path(git_service.ensure_config(str(tmp_path), "demo"))
    data = yaml.safe_load(config_path.read_text())

    assert data["runtime"]["gpu"] is True
    assert data["apps"][0]["id"] == "gradio"
    assert data["apps"][0]["port"] == 7860


def test_register_existing_returns_detection_and_registers(monkeypatch, tmp_path):
    registered = {}

    def fake_register(project_id, name, path):
        registered.update({"project_id": project_id, "name": name, "path": path})

    monkeypatch.setattr("capsulelab.db.repositories.projects.register", fake_register)
    (tmp_path / "requirements.txt").write_text("jupyterlab==4.2.0\n")

    result = git_service.register_existing(str(tmp_path), name="demo")

    assert result["project_id"] == "cap-demo"
    assert result["detected"]["app_ids"] == ["jupyter"]
    assert registered["name"] == "demo"


def test_history_parses_git_log(monkeypatch, tmp_path):
    def fake_run(args, cwd=None):
        if args[:2] == ["git", "rev-parse"]:
            return "true"
        if args[:2] == ["git", "log"]:
            return "abc123\tAda\t2026-05-25\tInitial commit\nbcd234\tGrace\t2026-05-24\tAdd app"
        raise AssertionError(args)

    monkeypatch.setattr(git_service, "_run", fake_run)

    commits = git_service.history(str(tmp_path), limit=2)

    assert commits[0] == {"hash": "abc123", "author": "Ada", "date": "2026-05-25", "subject": "Initial commit"}
    assert len(commits) == 2


def test_branches_marks_current(monkeypatch, tmp_path):
    def fake_run(args, cwd=None):
        if args[:2] == ["git", "rev-parse"]:
            return "true"
        if args[:2] == ["git", "branch"]:
            return "  feature\n* main"
        raise AssertionError(args)

    monkeypatch.setattr(git_service, "_run", fake_run)

    result = git_service.branches(str(tmp_path))

    assert result["current"] == "main"
    assert result["branches"] == [
        {"name": "feature", "current": False},
        {"name": "main", "current": True},
    ]


def test_commit_returns_clean_without_changes(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        if args[:2] == ["git", "rev-parse"]:
            return "true"
        if args == ["git", "add", "-A"]:
            return ""
        if args == ["git", "status", "--porcelain"]:
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(git_service, "_run", fake_run)

    result = git_service.commit(str(tmp_path), "demo")

    assert result["status"] == "clean"
    assert ["git", "commit", "-m", "demo"] not in calls


def test_publish_adds_remote_and_pushes_current_branch(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        if args[:2] == ["git", "rev-parse"]:
            return "true"
        if args == ["git", "remote"]:
            return ""
        if args[:3] == ["git", "remote", "add"]:
            return ""
        if args == ["git", "branch", "--show-current"]:
            return "main"
        if args[:2] == ["git", "push"]:
            return "pushed"
        raise AssertionError(args)

    monkeypatch.setattr(git_service, "_run", fake_run)

    result = git_service.publish(str(tmp_path), "git@example.test:demo/project.git")

    assert result["status"] == "published"
    assert ["git", "remote", "add", "origin", "git@example.test:demo/project.git"] in calls
    assert ["git", "push", "-u", "origin", "main"] in calls
