from pathlib import Path

from capsulelab.db import sqlite
from capsulelab.db.repositories import builds, projects
from capsulelab.services import build_assistant_service


def _setup_project(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")
    sqlite.init_db()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".workbench").mkdir()
    (project / ".workbench" / "project.yaml").write_text("name: demo\nruntime:\n  image: demo:dev\n")
    (project / "Dockerfile").write_text("FROM python:3.12-slim\n")
    projects.register("cap-demo", "demo", str(project))
    return project


def test_analyze_failed_build_reports_context_and_pip_suggestion(monkeypatch, tmp_path):
    project = _setup_project(monkeypatch, tmp_path)
    (project / "requirements.txt").write_text("missing-package==0.0.1\n")
    builds.add_log(
        "cap-demo",
        "demo:dev",
        "failed",
        "ERROR: Could not find a version that satisfies the requirement missing-package==0.0.1",
    )

    report = build_assistant_service.analyze_failed_build("cap-demo")

    assert report.build_status == "failed"
    assert "Dockerfile" in report.context_files
    assert report.findings[0].label == "Python package resolution failed"
    assert report.proposed_edits[0].path == "preBuild.bash"
    assert "pip install --upgrade" in report.proposed_edits[0].content
    assert report.review_required is True
    assert report.rebuild_triggered is False


def test_analyze_failed_build_without_logs_is_informational(monkeypatch, tmp_path):
    _setup_project(monkeypatch, tmp_path)

    report = build_assistant_service.analyze_failed_build("cap-demo")

    assert report.build_status == "missing"
    assert report.findings[0].severity == "info"
    assert report.proposed_edits == []


def test_apply_first_proposed_edit_writes_only_build_script(monkeypatch, tmp_path):
    _setup_project(monkeypatch, tmp_path)
    builds.add_log(
        "cap-demo",
        "demo:dev",
        "failed",
        "ERROR: No matching distribution found for demo",
    )

    result = build_assistant_service.apply_first_proposed_edit("cap-demo")

    assert result["applied"] is True
    script = Path(result["path"])
    assert script.name == "preBuild.bash"
    assert "CapsuleLab build assistant suggestion" in script.read_text()


def test_apply_proposed_edit_rejects_non_build_script(tmp_path):
    edit = build_assistant_service.ProposedBuildEdit(
        path="requirements.txt",
        action="append",
        content="demo",
        rationale="not allowed",
    )

    try:
        build_assistant_service.apply_proposed_edit(str(tmp_path), edit)
    except ValueError as exc:
        assert "preBuild.bash" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
