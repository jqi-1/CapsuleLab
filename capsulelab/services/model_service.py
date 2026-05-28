import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from capsulelab.core.document_store import DocumentStore

MODEL_STORE = DocumentStore(Path.home() / ".capsulelab" / "models.json", default={"models": []})


@dataclass
class ModelRecord:
    id: str
    name: str
    version: str
    source: str
    path: str
    sha256: str
    size_bytes: int
    metadata: dict[str, Any]


def _load() -> list[ModelRecord]:
    data = MODEL_STORE.read()
    return [ModelRecord(**row) for row in data.get("models", [])]


def _save(records: list[ModelRecord]) -> None:
    MODEL_STORE.write({"models": [asdict(record) for record in records]})


def register_model(
    name: str,
    version: str,
    path: str,
    source: str = "local",
    metadata: dict[str, Any] | None = None,
) -> dict:
    artifact = Path(path).expanduser().resolve()
    if not artifact.exists() or not artifact.is_file():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    records = _load()
    record = ModelRecord(
        id=str(uuid4()),
        name=name,
        version=version,
        source=source,
        path=str(artifact),
        sha256=sha256_file(artifact),
        size_bytes=artifact.stat().st_size,
        metadata=metadata or {},
    )
    records = [existing for existing in records if not (existing.name == name and existing.version == version)]
    records.append(record)
    _save(records)
    return asdict(record)


def list_models(name: str | None = None) -> list[dict]:
    records = _load()
    if name:
        records = [record for record in records if record.name == name]
    return [asdict(record) for record in sorted(records, key=lambda item: (item.name, item.version))]


def get_model(model_id: str) -> dict | None:
    for record in _load():
        if record.id == model_id:
            return asdict(record)
    return None


def verify_model(model_id: str) -> dict:
    record = get_model(model_id)
    if not record:
        raise ValueError(f"Model '{model_id}' not found")
    path = Path(record["path"])
    if not path.exists():
        return {**record, "ok": False, "error": "Model artifact path does not exist"}
    digest = sha256_file(path)
    return {
        **record,
        "ok": digest == record["sha256"],
        "current_sha256": digest,
        "error": "" if digest == record["sha256"] else "SHA-256 digest mismatch",
    }


def remove_model(model_id: str) -> bool:
    records = _load()
    kept = [record for record in records if record.id != model_id]
    if len(kept) == len(records):
        return False
    _save(kept)
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
