import yaml

from capsulelab.services import environment_service


def write_project(tmp_path):
    workbench = tmp_path / ".workbench"
    workbench.mkdir()
    (workbench / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "demo",
                "runtime": {"type": "docker", "dockerfile": "Dockerfile", "image": "demo:dev", "gpu": False},
                "environment": {"PYTHONPATH": "/workspace"},
            }
        )
    )
    (tmp_path / "requirements.txt").write_text("# base\npandas==2.2.0\n\n")


def test_describe_reads_dependencies_environment_and_runtime(tmp_path):
    write_project(tmp_path)

    result = environment_service.describe(str(tmp_path))

    assert result["runtime"]["image"] == "demo:dev"
    assert result["dependency_file"] == "requirements.txt"
    assert result["dependency_file_exists"] is True
    assert result["dependencies"] == ["pandas==2.2.0"]
    assert result["environment"] == {"PYTHONPATH": "/workspace"}


def test_add_dependency_appends_once(tmp_path):
    write_project(tmp_path)

    environment_service.add_dependency(str(tmp_path), "numpy>=2")
    result = environment_service.add_dependency(str(tmp_path), "numpy>=2")

    assert result["dependencies"] == ["pandas==2.2.0", "numpy>=2"]
    assert (tmp_path / "requirements.txt").read_text().count("numpy>=2") == 1


def test_set_and_remove_environment_variable_updates_project_yaml(tmp_path):
    write_project(tmp_path)

    updated = environment_service.set_environment_variable(str(tmp_path), "TOKENIZERS_PARALLELISM", "false")
    removed = environment_service.remove_environment_variable(str(tmp_path), "PYTHONPATH")

    assert updated["environment"]["TOKENIZERS_PARALLELISM"] == "false"
    assert "PYTHONPATH" not in removed["environment"]
    data = yaml.safe_load((tmp_path / ".workbench" / "project.yaml").read_text())
    assert data["environment"] == {"TOKENIZERS_PARALLELISM": "false"}
