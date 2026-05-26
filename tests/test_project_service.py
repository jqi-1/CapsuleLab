import pytest
from pathlib import Path
import tempfile
import os
import yaml
from backend.services import project_service
from backend.models.project import ProjectConfig, RuntimeConfig, AppConfig


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
