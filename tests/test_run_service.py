from capsulelab.db import sqlite
from capsulelab.db.repositories import projects, runs
from capsulelab.services import run_service


def test_finish_run_can_be_scoped_to_project(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-one", "one", str(tmp_path))
    runs.create("run-1", "cap-one", "one")

    run_service.finish_run("run-1", "finished", project_id="cap-two")

    rows = runs.list("cap-one")
    assert rows[0]["status"] == "running"

    run_service.finish_run("run-1", "finished", project_id="cap-one")

    rows = runs.list("cap-one")
    assert rows[0]["status"] == "finished"
