"""Integration tests for the canonical CLI workflow:

  cap init demo --template python-basic
  cap doctor
  cap build
  cap start
  cap app start jupyter
  cap app open jupyter
  cap stop

Pure-config tests (pytest -m pure_config) validate init, doctor with mocked
infrastructure, and URL generation.  No Docker needed.

Docker-marked tests (pytest -m docker) exercise the full container lifecycle
and require a running Docker daemon.
"""

import os
import socket
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from cli.main import cli

runner = CliRunner()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def project_name() -> str:
    return f"clitest{os.urandom(4).hex()}"


@pytest.fixture
def init_project(tmp_path: Path, project_name: str) -> Path:
    """Run ``cap init <name> --template python-basic --path <dir>`` and return
    the project directory."""
    proj_dir = tmp_path / project_name
    result = runner.invoke(
        cli,
        [
            "init",
            project_name,
            "--template",
            "python-basic",
            "--path",
            str(proj_dir),
        ],
    )
    assert result.exit_code == 0, f"cap init failed:\n{result.output}"
    return proj_dir


# ── Pure-config tests (no Docker) ─────────────────────────────────────────────


@pytest.mark.pure_config
class TestInit:
    """``cap init`` project creation and structure."""

    def test_creates_project_directory(self, init_project: Path) -> None:
        assert init_project.is_dir()

    def test_creates_expected_structure(self, init_project: Path) -> None:
        assert (init_project / ".workbench" / "project.yaml").is_file()
        assert (init_project / "Dockerfile").is_file()
        assert (init_project / "requirements.txt").is_file()
        assert (init_project / "README.md").is_file()
        assert (init_project / ".dockerignore").is_file()
        assert (init_project / "notebooks").is_dir()
        assert (init_project / "data").is_dir()
        assert (init_project / "src").is_dir()

    def test_project_yaml_name(self, init_project: Path, project_name: str) -> None:
        import yaml

        config = yaml.safe_load((init_project / ".workbench" / "project.yaml").read_text())
        assert config["name"] == project_name

    def test_project_yaml_includes_jupyter_app(self, init_project: Path) -> None:
        import yaml

        config = yaml.safe_load((init_project / ".workbench" / "project.yaml").read_text())
        app_ids = [a["id"] for a in config.get("apps", [])]
        assert "jupyter" in app_ids

    def test_init_requires_name(self) -> None:
        result = runner.invoke(cli, ["init"])
        assert result.exit_code != 0
        assert "required" in result.output.lower()

    def test_init_invalid_template(self, tmp_path: Path) -> None:
        result = runner.invoke(cli, ["init", "x", "--template", "nonexistent", "--path", str(tmp_path)])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


@pytest.mark.pure_config
class TestDoctor:
    """``cap doctor`` with all external dependencies stubbed."""

    @pytest.fixture(autouse=True)
    def _stub_externals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import capsulelab.services.doctor_service as ds

        monkeypatch.setattr(ds.docker_service, "check_docker_status", _docker_ok)
        monkeypatch.setattr(ds.gpu_service, "get_gpu_info", _gpu_none)
        monkeypatch.setattr(ds.gpu_service, "docker_gpu_available", lambda: False)
        monkeypatch.setattr(ds.secrets_service, "missing_required_secrets", lambda pid, cfg: [])
        monkeypatch.setattr(ds.git_service, "git_status", _git_ok)
        monkeypatch.setattr(ds.compose_service, "status", _compose_none)
        monkeypatch.setattr(ds.image_service, "byoc_checks", lambda path, df: [])
        monkeypatch.setattr("capsulelab.db.repositories.projects.list", lambda: [])
        monkeypatch.setattr("capsulelab.db.repositories.builds.get_metadata", lambda pid: None)

    def test_doctor_passes_on_fresh_project(self, init_project: Path) -> None:
        result = runner.invoke(cli, ["doctor", "--path", str(init_project)])
        assert result.exit_code == 0, f"doctor failed:\n{result.output}"
        assert "Config file" in result.output
        assert "Dockerfile" in result.output

    def test_doctor_json_output(self, init_project: Path) -> None:
        import json

        result = runner.invoke(cli, ["doctor", "--path", str(init_project), "--json"])
        assert result.exit_code == 0, f"doctor --json failed:\n{result.output}"
        data = json.loads(result.output)
        assert data["project_name"] == init_project.name
        assert "checks" in data
        assert isinstance(data["all_ok"], bool)

    def test_doctor_fails_on_missing_dockerfile(self, tmp_path: Path) -> None:
        import yaml

        proj = tmp_path / "nodocker"
        (proj / ".workbench").mkdir(parents=True)
        (proj / ".workbench" / "project.yaml").write_text(
            yaml.safe_dump(
                {
                    "name": "nodocker",
                    "runtime": {
                        "type": "docker",
                        "dockerfile": "Dockerfile",
                        "image": "nodocker:dev",
                    },
                }
            )
        )
        result = runner.invoke(cli, ["doctor", "--path", str(proj)])
        assert result.exit_code != 0
        assert "Missing" in result.output or "error" in result.output.lower()


@pytest.mark.pure_config
class TestAppOpen:
    """``cap app open`` URL generation (no browser launched in tests)."""

    def test_generates_localhost_url(self) -> None:
        from capsulelab.core.project import AppConfig
        from capsulelab.services.app_service import get_app_url

        cfg = AppConfig(
            name="JupyterLab",
            id="jupyter",
            command="jupyter lab --ip=0.0.0.0 --port=8899 --no-browser --allow-root",
            port=8899,
            url_path="/",
        )
        assert get_app_url(cfg) == "http://localhost:8899/"

    def test_app_open_via_cli_accepts_app_id(self, init_project: Path) -> None:
        """The open subcommand accepts a valid app id without error
        (it just prints the URL, no browser is actually opened in CI)."""
        result = runner.invoke(cli, ["app", "open", "jupyter", "--path", str(init_project)])
        assert result.exit_code == 0
        assert "8899" in result.output


# ── Docker-dependent tests ────────────────────────────────────────────────────


@pytest.mark.docker
class TestDockerWorkflow:
    """Full container lifecycle exercised through the CLI.

    Build → start → app start jupyter → app list → stop.

    Marked ``pytest.mark.docker`` — auto-skipped when no Docker daemon
    is available (see ``conftest.py``).
    """

    @pytest.fixture(autouse=True)
    def _workdir(self, init_project: Path, project_name: str) -> None:
        self.project = init_project
        self.name = project_name

    def build(self) -> None:
        r = runner.invoke(cli, ["build", "--path", str(self.project)])
        assert r.exit_code == 0, f"build failed:\n{r.output}"
        assert "built" in r.output.lower()

    def start(self) -> None:
        r = runner.invoke(cli, ["start", "--path", str(self.project)])
        assert r.exit_code == 0, f"start failed:\n{r.output}"
        assert "started" in r.output.lower() or "already running" in r.output.lower()

    def stop(self) -> None:
        r = runner.invoke(cli, ["stop", "--path", str(self.project)])
        assert r.exit_code == 0, f"stop failed:\n{r.output}"

    def test_build(self) -> None:
        self.build()

    def test_start_then_stop(self) -> None:
        self.build()
        self.start()
        self.stop()

    def test_full_lifecycle(self) -> None:
        """Build → start → app start jupyter → app list → stop."""
        self.build()
        self.start()

        # Use a free port so test never conflicts with other containers
        free_port = _free_port()
        config_path = self.project / ".workbench" / "project.yaml"
        config = yaml.safe_load(config_path.read_text())
        for app in config.get("apps", []):
            if app["id"] == "jupyter":
                app["port"] = free_port
                app["command"] = app["command"].replace("8899", str(free_port))
        config_path.write_text(yaml.dump(config, sort_keys=False))

        # app start jupyter
        r = runner.invoke(cli, ["app", "start", "jupyter", "--path", str(self.project)])
        assert r.exit_code == 0, f"app start failed:\n{r.output}"
        assert "running" in r.output.lower()

        # app list
        r = runner.invoke(cli, ["app", "list", "--path", str(self.project)])
        assert r.exit_code == 0
        assert "jupyter" in r.output.lower()

        self.stop()


# ── Fake helpers for pure tests ───────────────────────────────────────────────


def _docker_ok():
    from capsulelab.services.docker_service import DockerStatus

    return DockerStatus(
        available=True,
        binary_found=True,
        daemon_running=True,
        socket_accessible=True,
        version="25.0.0",
    )


def _gpu_none():
    from capsulelab.services.gpu_service import GpuInfo

    return GpuInfo(available=False, name="", vram_mb=0)


def _git_ok(_project_path: str = ""):
    return {
        "is_repo": True,
        "branch": "main",
        "remote": "origin",
        "dirty_files": 0,
        "lfs_available": True,
    }


def _compose_none(_project_path: str = ""):
    return {
        "available": False,
        "binary": "",
        "compose_file": None,
        "detected": False,
        "services": [],
        "error": "",
    }
