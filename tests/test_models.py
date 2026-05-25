import pytest
from backend.models.project import ProjectConfig, RuntimeConfig, AppConfig, Mount, RuntimeType


def test_project_config_minimal():
    config = ProjectConfig(
        name="test",
        runtime=RuntimeConfig(image="test:dev"),
    )
    assert config.name == "test"
    assert config.runtime.image == "test:dev"
    assert config.runtime.type == RuntimeType.docker
    assert len(config.mounts) == 1
    assert config.mounts[0].source == "."


def test_project_config_full():
    config = ProjectConfig(
        name="full-test",
        description="A full test",
        runtime=RuntimeConfig(
            type="docker",
            dockerfile="Dockerfile",
            image="test:latest",
            gpu=True,
        ),
        mounts=[
            Mount(source="./data", target="/data"),
            Mount(source="./models", target="/models", read_only=True),
        ],
        environment={"PYTHONPATH": "/workspace"},
        apps=[
            AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888),
            AppConfig(name="Streamlit", id="streamlit", command="streamlit run app.py", port=8501),
        ],
    )
    assert config.name == "full-test"
    assert config.runtime.gpu is True
    assert len(config.mounts) == 2
    assert config.mounts[1].read_only is True
    assert len(config.apps) == 2
    assert config.apps[0].id == "jupyter"


def test_invalid_runtime_type():
    with pytest.raises(ValueError):
        RuntimeConfig(type="invalid", image="test:dev")
