from backend.db import sqlite
from backend.services import secrets_service


def test_default_secret_upsert_does_not_duplicate(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()

    secrets_service.set_secret("cap-demo", "HF_TOKEN", "one")
    secrets_service.set_secret("cap-demo", "HF_TOKEN", "two")

    rows = secrets_service.list_secret_presence("cap-demo")

    assert len(rows) == 1
    assert rows[0]["name"] == "HF_TOKEN"
    assert rows[0]["location"] is None
