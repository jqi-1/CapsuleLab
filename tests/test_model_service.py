from fastapi import HTTPException

from backend.api import models
from capsulelab.core.document_store import DocumentStore
from capsulelab.services import model_service


def _use_tmp_store(tmp_path):
    store = DocumentStore(tmp_path / "models.json", default={"models": []})
    model_service.MODEL_STORE = store
    return store


def test_register_list_verify_and_remove_model(tmp_path, monkeypatch):
    _use_tmp_store(tmp_path)
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"model-data")

    record = model_service.register_model("demo-model", "1.0", str(artifact), source="local")
    listed = model_service.list_models("demo-model")
    verified = model_service.verify_model(record["id"])

    assert listed[0]["name"] == "demo-model"
    assert listed[0]["version"] == "1.0"
    assert verified["ok"] is True

    artifact.write_bytes(b"changed")
    failed = model_service.verify_model(record["id"])
    assert failed["ok"] is False
    assert "mismatch" in failed["error"]

    assert model_service.remove_model(record["id"]) is True
    assert model_service.list_models() == []


def test_register_model_replaces_same_name_and_version(tmp_path, monkeypatch):
    _use_tmp_store(tmp_path)
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"one")
    first = model_service.register_model("demo", "1", str(artifact))
    artifact.write_bytes(b"two")
    second = model_service.register_model("demo", "1", str(artifact))

    records = model_service.list_models("demo")

    assert len(records) == 1
    assert records[0]["id"] == second["id"]
    assert records[0]["id"] != first["id"]


def test_model_api_maps_missing_artifact_to_404(tmp_path, monkeypatch):
    _use_tmp_store(tmp_path)

    try:
        models.register_model(
            models.RegisterModelRequest(name="missing", version="1", path=str(tmp_path / "missing.bin"))
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_model_api_verify_maps_missing_model_to_404(tmp_path, monkeypatch):
    _use_tmp_store(tmp_path)

    try:
        models.verify_model("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")
