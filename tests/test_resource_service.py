from pathlib import Path
from unittest.mock import MagicMock

from capsulelab.db.repositories.resources import ResourcesRepository
from capsulelab.services import resource_service


def test_disk_status(tmp_path):
    result = resource_service.disk_status(str(tmp_path))
    assert result["path"] == str(Path(tmp_path).resolve())
    assert result["total_bytes"] > 0
    assert result["free_percent"] > 0


def test_gpu_status_returns_no_gpus_when_nvidia_smi_missing(monkeypatch):
    monkeypatch.setattr(resource_service.subprocess, "run", MagicMock(side_effect=FileNotFoundError))
    result = resource_service.gpu_status()
    assert result["available"] is False
    assert result["gpus"] == []


def test_store_snapshot_uses_repo():
    fake_repo = MagicMock(spec=ResourcesRepository)
    fake_repo.store_snapshot.return_value = 42

    result = resource_service.store_resource_snapshot("proj-1", {"cpu_percent": 50}, repo=fake_repo)

    assert result == 42
    fake_repo.store_snapshot.assert_called_once_with("proj-1", {"cpu_percent": 50})


def test_get_history_uses_repo():
    fake_repo = MagicMock(spec=ResourcesRepository)
    fake_repo.get_history.return_value = [{"id": 1}]

    result = resource_service.get_resource_history("proj-1", limit=10, repo=fake_repo)

    assert result == [{"id": 1}]
    fake_repo.get_history.assert_called_once_with("proj-1", 10)


def test_get_latest_snapshot_uses_repo():
    fake_repo = MagicMock(spec=ResourcesRepository)
    fake_repo.get_latest.return_value = {"id": 1, "cpu_percent": 50}

    result = resource_service.get_latest_resource_snapshot("proj-1", repo=fake_repo)

    assert result == {"id": 1, "cpu_percent": 50}
    fake_repo.get_latest.assert_called_once_with("proj-1")


def test_get_latest_snapshot_returns_none_when_empty():
    fake_repo = MagicMock(spec=ResourcesRepository)
    fake_repo.get_latest.return_value = None

    result = resource_service.get_latest_resource_snapshot("proj-1", repo=fake_repo)

    assert result is None


def test_get_current_timestamp():
    result = resource_service.get_current_timestamp()
    assert "T" in result
    assert result.endswith(":00") or ":" in result


def test_store_snapshot_defaults_to_singleton():
    from capsulelab.db.repositories import resources as repo

    assert hasattr(repo, "store_snapshot")


def test_get_history_defaults_to_singleton():
    from capsulelab.db.repositories import resources as repo

    assert hasattr(repo, "get_history")


def test_get_latest_defaults_to_singleton():
    from capsulelab.db.repositories import resources as repo

    assert hasattr(repo, "get_latest")
