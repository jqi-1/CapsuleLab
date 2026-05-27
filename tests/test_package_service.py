import io
import tarfile

import yaml

from backend.services import package_service


def test_export_redacts_environment_and_machine_paths(tmp_path, monkeypatch):
    project = tmp_path / "demo"
    project.mkdir()
    (project / ".workbench").mkdir()
    (project / ".workbench" / "project.yaml").write_text(
        "name: demo\n"
        "runtime:\n"
        "  image: demo:dev\n"
        "mounts:\n"
        "  - source: /home/alice/private-data\n"
        "    target: /private\n"
        "datasets:\n"
        "  - name: private\n"
        "    path: /mnt/private-dataset\n"
        "    target: /data\n"
        "caches:\n"
        "  - source: /home/alice/.cache/huggingface\n"
        "    target: /root/.cache/huggingface\n"
        "secrets:\n"
        "  - name: API_KEY\n"
        "    location: local\n"
        "environment:\n"
        "  API_KEY: secret-value\n"
    )
    (project / ".env").write_text("API_KEY=secret-value\n")
    monkeypatch.setattr(package_service.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": str(project)})
    monkeypatch.setattr(package_service.builds, "get_metadata", lambda project_id: None)

    archive = package_service.export_project("cap-demo", str(tmp_path))

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        assert "demo/.env" not in names
        config = yaml.safe_load(tar.extractfile("demo/.workbench/project.yaml").read().decode("utf-8"))
        manifest = tar.extractfile("demo/.capsule-manifest.json").read().decode("utf-8")

    assert config["environment"]["API_KEY"] == ""
    assert config["mounts"][0]["source"] == ""
    assert config["datasets"][0]["path"] == ""
    assert config["caches"][0]["source"] == ""
    assert config["secrets"][0]["location"] is None
    assert "redactions" in manifest


def test_import_rejects_path_traversal_archive(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"bad"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    try:
        package_service.import_project(str(archive), str(tmp_path / "dest"))
    except ValueError as exc:
        assert "Unsafe archive member path" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
