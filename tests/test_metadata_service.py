from fastapi import HTTPException

from backend.api import metadata
from capsulelab.db import sqlite
from capsulelab.db.repositories import projects, secrets
from capsulelab.services import metadata_service


def test_backup_and_restore_excludes_secrets_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-demo", "demo", "/tmp/demo")
    secrets.set("cap-demo", "API_KEY", "secret-value")
    backup_path = tmp_path / "backup.json"

    backup = metadata_service.create_backup(str(backup_path))
    with sqlite.get_db() as conn:
        conn.execute("DELETE FROM secrets")
        conn.execute("DELETE FROM projects")
    restored = metadata_service.restore_backup(str(backup_path))

    assert backup["tables"]["projects"] == 1
    assert "secrets" not in backup["tables"]
    assert restored["restored"]["projects"] == 1
    assert restored["secrets_restored"] is False
    assert projects.get("cap-demo")["name"] == "demo"
    assert secrets.list("cap-demo") == []


def test_backup_and_restore_can_include_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-demo", "demo", "/tmp/demo")
    secrets.set("cap-demo", "API_KEY", "secret-value")
    backup_path = tmp_path / "backup.json"

    backup = metadata_service.create_backup(str(backup_path), include_secrets=True)
    with sqlite.get_db() as conn:
        conn.execute("DELETE FROM secrets")
        conn.execute("DELETE FROM projects")
    restored = metadata_service.restore_backup(str(backup_path), include_secrets=True)

    assert backup["tables"]["secrets"] == 1
    assert restored["secrets_restored"] is True
    assert secrets.list("cap-demo")[0]["name"] == "API_KEY"


def test_inspect_backup_reports_table_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-demo", "demo", "/tmp/demo")
    backup_path = tmp_path / "backup.json"
    metadata_service.create_backup(str(backup_path))

    info = metadata_service.inspect_backup(str(backup_path))

    assert info["backup_version"] == metadata_service.BACKUP_VERSION
    assert info["tables"]["projects"] == 1


def test_metadata_api_maps_missing_backup_to_400():
    try:
        metadata.inspect_backup("/tmp/does-not-exist-capsulelab-backup.json")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")
