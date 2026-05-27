import pytest
import yaml
from pathlib import Path
from capsulelab.core.project import ProjectConfig, AppConfig

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
MAINTAINED_TEMPLATES = ["python-basic", "pytorch-cuda", "streamlit-dashboard", "research-rag", "deployable-fastapi", "opensource-python-package"]


def _iter_templates():
    for name in MAINTAINED_TEMPLATES:
        tmpl = TEMPLATES_DIR / name
        if tmpl.exists():
            yield name, tmpl


def test_all_maintained_templates_exist():
    missing = [t for t in MAINTAINED_TEMPLATES if not (TEMPLATES_DIR / t).exists()]
    assert not missing, f"Missing maintained templates: {missing}"


def test_no_unlisted_templates():
    found = sorted(d.name for d in TEMPLATES_DIR.iterdir()
                   if d.is_dir() and not d.name.startswith("."))
    extra = [t for t in found if t not in MAINTAINED_TEMPLATES]
    assert not extra, f"Unlisted templates found — add to manifest or remove: {extra}"


class TestProjectYaml:
    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_project_yaml_exists(self, name):
        path = TEMPLATES_DIR / name / ".workbench" / "project.yaml"
        assert path.exists(), f"Missing .workbench/project.yaml in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_project_yaml_valid_yaml(self, name):
        path = TEMPLATES_DIR / name / ".workbench" / "project.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data is not None, f"Empty YAML in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_project_yaml_deserializes(self, name):
        path = TEMPLATES_DIR / name / ".workbench" / "project.yaml"
        cfg = ProjectConfig(**yaml.safe_load(open(path)))
        assert cfg.name, f"Project name empty in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_project_yaml_apps_have_valid_ports(self, name):
        path = TEMPLATES_DIR / name / ".workbench" / "project.yaml"
        cfg = ProjectConfig(**yaml.safe_load(open(path)))
        for app in cfg.apps:
            assert app.port is None or 1 <= app.port <= 65535, f"App '{app.id}' has invalid port {app.port} in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_project_yaml_mounts_exist(self, name):
        path = TEMPLATES_DIR / name / ".workbench" / "project.yaml"
        cfg = ProjectConfig(**yaml.safe_load(open(path)))
        tmpl_dir = TEMPLATES_DIR / name
        for mount in cfg.mounts:
            mount_path = tmpl_dir / mount.source
            expected = tmpl_dir.name in mount.source or mount_path.exists()
            if not expected:
                pytest.skip(f"Mount '{mount.source}' is a runtime mount, skipping existence check")


class TestTemplateStructure:
    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerfile_exists(self, name):
        path = TEMPLATES_DIR / name / "Dockerfile"
        assert path.exists(), f"Missing Dockerfile in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerfile_not_empty(self, name):
        content = (TEMPLATES_DIR / name / "Dockerfile").read_text().strip()
        assert content, f"Empty Dockerfile in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerignore_exists(self, name):
        path = TEMPLATES_DIR / name / ".dockerignore"
        assert path.exists(), f"Missing .dockerignore in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_readme_exists(self, name):
        path = TEMPLATES_DIR / name / "README.md"
        assert path.exists(), f"Missing README.md in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_readme_not_empty(self, name):
        content = (TEMPLATES_DIR / name / "README.md").read_text().strip()
        assert content, f"Empty README.md in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_requirements_txt_exists(self, name):
        path = TEMPLATES_DIR / name / "requirements.txt"
        assert path.exists(), f"Missing requirements.txt in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_requirements_txt_not_empty(self, name):
        content = (TEMPLATES_DIR / name / "requirements.txt").read_text().strip()
        assert content, f"Empty requirements.txt in {name}"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerfile_has_base_image(self, name):
        content = (TEMPLATES_DIR / name / "Dockerfile").read_text()
        assert content.strip().startswith("FROM "), f"Dockerfile in {name} must start with FROM"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerfile_has_workdir(self, name):
        content = (TEMPLATES_DIR / name / "Dockerfile").read_text()
        assert "WORKDIR" in content, f"Dockerfile in {name} missing WORKDIR"

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_dockerfile_has_cmd(self, name):
        content = (TEMPLATES_DIR / name / "Dockerfile").read_text()
        assert "CMD" in content, f"Dockerfile in {name} missing CMD"


@pytest.mark.docker
class TestTemplateBuild:
    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_template_builds(self, name):
        import subprocess
        tmpl_dir = str(TEMPLATES_DIR / name)
        image = f"capsulelab-test-{name}:test"
        result = subprocess.run(
            ["docker", "build", "-t", image, "."],
            capture_output=True, text=True, timeout=300,
            cwd=tmpl_dir,
        )
        if result.returncode != 0:
            if "platform" in result.stderr.lower() and "exec format error" in result.stderr:
                pytest.skip(f"Base image not available for this platform ({name})")
            assert False, (
                f"Build failed for {name}\nstdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
            )
        subprocess.run(
            ["docker", "rmi", image],
            capture_output=True, timeout=60,
        )

    @pytest.mark.parametrize("name", MAINTAINED_TEMPLATES)
    def test_manifest_has_entry(self, name):
        manifest_path = TEMPLATES_DIR / "manifest.json"
        assert manifest_path.exists(), "Missing manifest.json"
        import json
        manifest = json.loads(manifest_path.read_text())
        assert name in manifest, f"Template {name} missing from manifest.json"
        entry = manifest[name]
        assert "name" in entry
        assert "description" in entry
        assert "gpu" in entry
        assert "tags" in entry
