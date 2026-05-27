from capsulelab.core.project import Cache, Dataset, ProjectConfig, RuntimeConfig, SecretRef
from capsulelab.services import location_override_service


def test_apply_location_overrides_uses_local_fallbacks(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config = ProjectConfig(
        name="demo",
        runtime=RuntimeConfig(image="demo:dev"),
        datasets=[Dataset(name="sample", path="data", target="/data")],
        caches=[Cache(source=str(cache_dir), target="/cache")],
        secrets=[SecretRef(name="API_KEY", location="local")],
    )

    result = location_override_service.apply_location_overrides(config, str(tmp_path))

    assert result["datasets"][0]["path"] == str(data_dir)
    assert result["datasets"][0]["exists"] is True
    assert result["caches"][0]["source"] == str(cache_dir)
    assert result["caches"][0]["exists"] is True
    assert result["secrets"][0]["location"] == "local"


def test_apply_location_overrides_uses_remote_values(monkeypatch, tmp_path):
    config = ProjectConfig(
        name="demo",
        runtime=RuntimeConfig(image="demo:dev"),
        datasets=[Dataset(name="sample", path="data", target="/data")],
        caches=[Cache(source="~/.cache/huggingface", target="/cache")],
        secrets=[SecretRef(name="API_KEY")],
    )

    def fake_get_override(location_id, override_type, logical_name):
        values = {
            ("dataset", "sample"): "/mnt/datasets/sample",
            ("cache", "~/.cache/huggingface"): "/mnt/cache/hf",
            ("secret", "API_KEY"): "remote-vault",
        }
        value = values.get((override_type, logical_name))
        return {"value": value} if value else None

    monkeypatch.setattr(location_override_service.locations, "get_override", fake_get_override)

    result = location_override_service.apply_location_overrides(config, str(tmp_path), location_id="loc-demo")

    assert result["datasets"][0]["path"] == "/mnt/datasets/sample"
    assert result["datasets"][0]["exists"] is None
    assert result["caches"][0]["source"] == "/mnt/cache/hf"
    assert result["caches"][0]["exists"] is None
    assert result["secrets"][0]["location"] == "remote-vault"
