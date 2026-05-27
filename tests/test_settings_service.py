from fastapi import HTTPException

from backend.api import settings
from backend.db import sqlite
from backend.services import settings_service


def test_settings_defaults_set_get_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")

    assert settings_service.get_setting("runtime.default") == "docker"
    result = settings_service.set_setting("runtime.default", "podman")
    assert result == {"key": "runtime.default", "value": "podman"}
    assert settings_service.get_setting("runtime.default") == "podman"
    assert settings_service.remove_setting("runtime.default") is True
    assert settings_service.get_setting("runtime.default") == "docker"


def test_settings_rejects_unknown_key(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "db" / "capsulelab.db")

    try:
        settings_service.set_setting("unknown", "value")
    except ValueError as exc:
        assert "Unsupported setting" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_settings_api_maps_unknown_key_to_400():
    try:
        settings.set_setting("unknown", settings.SetSettingRequest(value="x"))
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")
