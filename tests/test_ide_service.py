from backend.services import ide_service


def test_setup_cursor_writes_ai_workbench_rules(tmp_path):
    result = ide_service.setup_ide(str(tmp_path), "cursor", project_name="demo")
    rules = tmp_path / ".cursor" / "rules" / "ai-workbench" / "capsulelab.mdc"

    assert str(rules) in result["files"]
    text = rules.read_text()
    assert "CapsuleLab / AI Workbench-style Container Guidance" in text
    assert "cap build" in text
    assert "cap project git status" in text


def test_setup_vscode_writes_dev_container_extension_recommendation(tmp_path):
    result = ide_service.setup_ide(str(tmp_path), "vscode", project_name="demo")
    extensions = tmp_path / ".vscode" / "extensions.json"

    assert str(extensions) in result["files"]
    assert "ms-vscode-remote.remote-containers" in extensions.read_text()


def test_setup_all_writes_supported_ide_files(tmp_path):
    result = ide_service.setup_ide(str(tmp_path), "all", project_name="demo")

    assert result["ide"] == "all"
    assert (tmp_path / ".cursor" / "rules" / "ai-workbench" / "capsulelab.mdc").exists()
    assert (tmp_path / ".vscode" / "extensions.json").exists()
    assert (tmp_path / ".windsurf" / "rules" / "capsulelab.md").exists()


def test_attach_instructions_include_container_and_workspace(tmp_path):
    result = ide_service.attach_instructions(str(tmp_path), "cursor", project_name="Demo Project")

    assert result["container"] == "cap-demo-project"
    assert result["workspace"] == "/workspace"
    assert any("Dev Containers" in step for step in result["instructions"])


def test_setup_ide_rejects_unknown_ide(tmp_path):
    try:
        ide_service.setup_ide(str(tmp_path), "unknown", project_name="demo")
    except ValueError as exc:
        assert "Unsupported IDE" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
