import pytest
from pathlib import Path
import tempfile
import os
import yaml
from capsulelab.services import project_service
from capsulelab.core.project import ProjectConfig, RuntimeConfig, AppConfig


@pytest.mark.pure_config
def test_create_from_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpl_dir = Path(tmpdir) / "template"
        tmpl_dir.mkdir()
        (tmpl_dir / ".workbench").mkdir()
        config = {
            "name": "placeholder",
            "runtime": {"type": "docker", "dockerfile": "Dockerfile", "image": "placeholder:dev"},
            "mounts": [{"source": ".", "target": "/workspace"}],
            "apps": [{"name": "Jupyter", "id": "jupyter", "command": "jupyter lab", "port": 8888}],
        }
        with open(tmpl_dir / ".workbench" / "project.yaml", "w") as f:
            yaml.dump(config, f)

        dest = Path(tmpdir) / "my-project"
        project_service.create_from_template("my-project", str(tmpl_dir), str(dest))

        assert (dest / ".workbench" / "project.yaml").exists()
        with open(dest / ".workbench" / "project.yaml") as f:
            loaded = yaml.safe_load(f)
        assert loaded["name"] == "my-project"
        assert loaded["runtime"]["image"] == "my-project:dev"


@pytest.mark.pure_config
def test_load_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "testproj"
        proj_dir.mkdir()
        (proj_dir / ".workbench").mkdir()
        config = {
            "name": "testproj",
            "runtime": {"type": "docker", "dockerfile": "Dockerfile", "image": "testproj:dev"},
        }
        with open(proj_dir / ".workbench" / "project.yaml", "w") as f:
            yaml.dump(config, f)

        loaded = project_service.load_config(str(proj_dir))
        assert loaded.name == "testproj"
        assert loaded.runtime.image == "testproj:dev"


@pytest.mark.pure_config
def test_load_config_reads_capsule_yaml_when_workbench_config_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "testproj"
        proj_dir.mkdir()
        config = {
            "schema_version": 1,
            "name": "testproj",
            "runtime": {"type": "docker", "dockerfile": "Dockerfile", "image": "testproj:dev"},
        }
        with open(proj_dir / "capsule.yaml", "w") as f:
            yaml.dump(config, f)

        loaded = project_service.load_config(str(proj_dir))

        assert loaded.name == "testproj"
        assert loaded.schema_version == project_service.CURRENT_SCHEMA_VERSION


@pytest.mark.pure_config
def test_load_config_prefers_workbench_project_yaml_over_capsule_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "testproj"
        proj_dir.mkdir()
        (proj_dir / ".workbench").mkdir()
        with open(proj_dir / "capsule.yaml", "w") as f:
            yaml.dump({"name": "capsule", "runtime": {"image": "capsule:dev"}}, f)
        with open(proj_dir / ".workbench" / "project.yaml", "w") as f:
            yaml.dump({"name": "canonical", "runtime": {"image": "canonical:dev"}}, f)

        loaded = project_service.load_config(str(proj_dir))

        assert loaded.name == "canonical"
        assert loaded.runtime.image == "canonical:dev"


@pytest.mark.pure_config
def test_migrate_manifest_writes_canonical_and_capsule_copy():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "testproj"
        proj_dir.mkdir()
        with open(proj_dir / "capsule.yaml", "w") as f:
            yaml.dump({"name": "testproj", "runtime": {"image": "testproj:dev"}}, f)

        result = project_service.migrate_manifest(str(proj_dir))

        canonical = Path(result["canonical"])
        capsule = Path(result["capsule"])
        assert canonical == proj_dir / ".workbench" / "project.yaml"
        assert canonical.exists()
        assert capsule.exists()
        data = yaml.safe_load(canonical.read_text())
        assert data["schema_version"] == project_service.CURRENT_SCHEMA_VERSION
        assert data["name"] == "testproj"


@pytest.mark.pure_config
def test_migrate_config_rejects_future_schema_version():
    with pytest.raises(ValueError, match="Unsupported project config schema_version"):
        project_service.migrate_config_data({"schema_version": 999, "name": "future"})


@pytest.mark.pure_config
def test_load_config_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError):
            project_service.load_config(tmpdir)


@pytest.mark.pure_config
def test_validate():
    config = ProjectConfig(
        name="test",
        runtime=RuntimeConfig(
            type="docker",
            dockerfile="Dockerfile",
            image="test:dev",
            gpu=True,
        ),
        apps=[AppConfig(name="Bad", id="bad", command="bad", port=99999)],
    )
    warnings = project_service.validate(config)
    assert any("invalid port" in w for w in warnings)


@pytest.mark.pure_config
def test_validate_web_app_requires_port():
    config = ProjectConfig(
        name="test",
        runtime=RuntimeConfig(image="test:dev"),
        apps=[AppConfig(name="Web", id="web", command="python app.py")],
    )

    warnings = project_service.validate(config)

    assert any("has no port" in w for w in warnings)


@pytest.mark.pure_config
def test_get_container_name():
    assert project_service.get_container_name("My Project") == "cap-my-project"
    assert project_service.get_container_name("test_project") == "cap-test-project"
    assert project_service.get_container_name("simple") == "cap-simple"


@pytest.mark.pure_config
def test_get_project_id():
    assert project_service.get_project_id("My Project") == "cap-my-project"
    assert project_service.get_project_id("test_project") == "cap-test-project"
    assert project_service.get_project_id("UPPERCASE") == "cap-uppercase"
