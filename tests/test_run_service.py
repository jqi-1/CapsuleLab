from backend.db import sqlite
from backend.services import run_service


def test_finish_run_can_be_scoped_to_project(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    sqlite.register_project("cap-one", "one", str(tmp_path))
    sqlite.create_run("run-1", "cap-one", "one")

    run_service.finish_run("run-1", "finished", project_id="cap-two")

    rows = sqlite.list_runs("cap-one")
    assert rows[0]["status"] == "running"

    run_service.finish_run("run-1", "finished", project_id="cap-one")

    rows = sqlite.list_runs("cap-one")
    assert rows[0]["status"] == "finished"
