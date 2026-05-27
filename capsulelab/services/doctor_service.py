import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from capsulelab.core.errors import Severity
from capsulelab.core.project import ProjectMode
from capsulelab.services import (
    compose_service,
    docker_service,
    gpu_service,
    project_service,
    git_service,
    secrets_service,
    image_service,
    profile_service,
)
from capsulelab.db.repositories import builds, projects


@dataclass
class DoctorCheck:
    label: str
    severity: Severity
    ok: bool
    detail: str = ""
    suggestion: str = ""


@dataclass
class DoctorReport:
    project_name: str
    project_path: str
    checks: list[DoctorCheck] = field(default_factory=list)

    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def errors(self) -> list[DoctorCheck]:
        return [c for c in self.checks if c.severity in (Severity.ERROR, Severity.CRITICAL) and not c.ok]

    def warnings(self) -> list[DoctorCheck]:
        return [c for c in self.checks if c.severity == Severity.WARNING and not c.ok]

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_path": self.project_path,
            "all_ok": self.all_ok(),
            "checks": [asdict(c) for c in self.checks],
        }


def _add(report: DoctorReport, label: str, ok: bool, detail: str = "", severity: Severity = Severity.INFO, suggestion: str = ""):
    report.checks.append(DoctorCheck(label=label, severity=severity, ok=ok, detail=detail, suggestion=suggestion))


def _registered_project_for_path(project_path: str) -> dict | None:
    resolved = str(Path(project_path).resolve())
    for project in projects.list():
        if str(Path(project["path"]).resolve()) == resolved:
            return project
    return None


def project_doctor(project_id: str) -> DoctorReport:
    row = projects.get(project_id)
    if not row:
        raise ValueError(f"Project '{project_id}' not found")
    return project_doctor_for_path(row["path"], project_id=project_id, project_name=row["name"])


def project_doctor_for_path(project_path: str, project_id: str | None = None, project_name: str | None = None) -> DoctorReport:
    project_path = str(Path(project_path).resolve())
    proj = Path(project_path)
    if not project_id:
        row = _registered_project_for_path(project_path)
        if row:
            project_id = row["id"]
            project_name = project_name or row["name"]

    report = DoctorReport(project_name=project_name or proj.name, project_path=project_path)

    try:
        config = project_service.load_config(project_path)
        report.project_name = project_name or config.name or proj.name
        _add(report, "Config file", True, f"Parsed .workbench/project.yaml — project: {config.name}")
    except Exception as e:
        _add(report, "Config file", False, str(e), Severity.ERROR)
        return report

    project_id = project_id or project_service.get_project_id(config.name)

    config_warnings = project_service.validate(config, project_path)
    for w in config_warnings:
        _add(report, "Config validation", False, w, Severity.WARNING)

    _add(report, "project.yaml: name", bool(config.name.strip()), config.name or "Empty name", Severity.WARNING)
    _add(report, "project.yaml: apps", bool(config.apps), f"{len(config.apps)} app(s) defined" if config.apps else "No apps configured", Severity.WARNING)
    _add(report, "project.yaml: runtime type", True, config.runtime.type.value)

    df_path = proj / config.runtime.dockerfile
    _add(report, "Dockerfile", df_path.exists(), "Found" if df_path.exists() else f"Missing {config.runtime.dockerfile}", Severity.ERROR)

    readme = proj / "README.md"
    has_readme = readme.exists()
    _add(report, "README.md", has_readme, "Found" if has_readme else "Missing", Severity.WARNING)
    if has_readme:
        readme_text = readme.read_text().strip()
        has_cmd = any(cmd in readme_text for cmd in ["cap doctor", "cap build", "cap start"])
        _add(report, "README: setup commands", has_cmd, "Mentions CapsuleLab commands" if has_cmd else "Missing cap doctor/build/start hints", Severity.WARNING)
        _add(report, "README: useful length", len(readme_text) >= 120, f"{len(readme_text)} chars", Severity.WARNING)

    package_files = [
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "Pipfile",
        "package.json",
    ]
    found_package_files = [name for name in package_files if (proj / name).exists()]
    _add(
        report,
        "Package manifest",
        bool(found_package_files),
        ", ".join(found_package_files) if found_package_files else "No Python/Conda/Node package manifest found",
        Severity.WARNING,
    )

    notebooks = list(proj.glob("*.ipynb")) + list((proj / "notebooks").glob("*.ipynb")) if (proj / "notebooks").exists() else list(proj.glob("*.ipynb"))
    _add(
        report,
        "Notebook/examples",
        bool(notebooks or config.apps),
        f"{len(notebooks)} notebook(s), {len(config.apps)} app(s)" if notebooks or config.apps else "No notebook or app entry point found",
        Severity.WARNING,
    )

    _add(
        report,
        "Template identity",
        _template_identity_known(proj),
        _template_identity_detail(proj),
        Severity.INFO,
    )

    dkr = docker_service.check_docker_status()
    if dkr.available:
        _add(report, "Docker", True, f"version {dkr.version}", Severity.INFO)
    elif not dkr.binary_found:
        _add(report, "Docker installed", False, dkr.error, Severity.CRITICAL, "Install Docker: https://docs.docker.com/engine/install/")
    elif not dkr.socket_accessible:
        _add(report, "Docker socket", False, dkr.error, Severity.ERROR, "Add user to docker group: sudo usermod -aG docker $USER")
    else:
        _add(report, "Docker daemon", False, dkr.error, Severity.CRITICAL, "Start Docker daemon")

    gpu_info = gpu_service.get_gpu_info()
    if gpu_info.available:
        _add(report, "GPU detected", True, f"{gpu_info.name} ({gpu_info.vram_mb} MB)", Severity.INFO)
        docker_gpu = gpu_service.docker_gpu_available()
        _add(report, "Docker GPU support", docker_gpu, "Available" if docker_gpu else "nvidia-container-toolkit not configured", Severity.WARNING)
    else:
        _add(report, "GPU detected", False, "No NVIDIA GPU found — running in CPU mode", Severity.INFO)

    if config.runtime.gpu and not gpu_info.available:
        _add(report, "GPU requested", False, "Project requires GPU but none detected", Severity.WARNING, "Install NVIDIA drivers and nvidia-container-toolkit")

    req_files = list(proj.glob("requirements*.txt")) + list(proj.glob("requirements/*.txt"))
    lockfiles = [proj / "poetry.lock", proj / "Pipfile.lock", proj / "uv.lock", proj / "requirements.lock"]
    has_lockfile = any("lock" in f.name.lower() for f in req_files) or any(f.exists() for f in lockfiles)
    _add(report, "Lockfile", has_lockfile, "Found" if has_lockfile else "No lockfile — use pip freeze, uv, or poetry", Severity.WARNING)

    reqs = proj / "requirements.txt"
    if reqs.exists():
        content = reqs.read_text()
        unpinned = [l for l in content.splitlines() if l.strip() and not l.startswith("#") and "==" not in l and ">=" not in l and l.strip() != ""]
        _add(report, "Pinned packages", not bool(unpinned), f"{len(unpinned)} unpinned" if unpinned else "All pinned", Severity.WARNING)

    build_meta = builds.get_metadata(project_id)
    if build_meta:
        _add(report, "Build metadata", True, f"Built at {build_meta['built_at']} — image: {build_meta['image']}", Severity.INFO)
    else:
        _add(report, "Build metadata", False, "No build metadata — run 'cap build' first", Severity.WARNING)

    _add_compose_checks(report, project_path, config.runtime.type.value)

    seen_ports: dict[int, str] = {}
    for app in config.apps:
        _add(report, f"App '{app.id}': command", bool(app.command.strip()), app.command or "Missing command", Severity.ERROR)
        if app.port is not None:
            port_ok = 1 <= app.port <= 65535 and app.port not in seen_ports
            detail = f":{app.port}"
            if app.port in seen_ports:
                detail = f"Port also used by {seen_ports[app.port]}"
            _add(report, f"App '{app.id}': port", port_ok, detail, Severity.ERROR)
            seen_ports[app.port] = app.id

    for mount in config.mounts:
        m_path = proj / mount.source if not Path(mount.source).is_absolute() else Path(mount.source)
        _add(report, f"Mount '{mount.source}'", m_path.exists(), "Found" if m_path.exists() else f"Path does not exist: {m_path}", Severity.WARNING)

    for cache in config.caches:
        c_path = Path(cache.source).expanduser()
        _add(report, f"Cache '{cache.source}'", c_path.exists(), f"Path: {c_path}" if c_path.exists() else f"Directory not found — will be skipped", Severity.WARNING)

    for dataset in config.datasets:
        d_path = proj / dataset.path if not Path(dataset.path).is_absolute() else Path(dataset.path)
        _add(report, f"Dataset '{dataset.name}'", d_path.exists(), f"Path: {d_path}" if d_path.exists() else f"Missing — place data at {d_path}", Severity.WARNING)

    for output_name in ["outputs", "runs", "mlruns"]:
        output_path = proj / output_name
        _add(
            report,
            f"Writable output '{output_name}'",
            _path_writable(output_path),
            f"Writable: {output_path}" if _path_writable(output_path) else f"Not writable or cannot create: {output_path}",
            Severity.WARNING,
        )

    missing_secrets = secrets_service.missing_required_secrets(project_id, config)
    _add(report, "Required secrets", not bool(missing_secrets),
         "All present" if not missing_secrets else f"Missing: {', '.join(missing_secrets)}",
         Severity.WARNING, "Set with: cap secrets set <name>")

    for check in image_service.byoc_checks(project_path, config.runtime.dockerfile):
        sev = Severity.ERROR if not check["ok"] else Severity.INFO
        _add(report, f"BYOC: {check['label']}", check["ok"], check["detail"], sev)

    try:
        git = git_service.git_status(project_path)
        if git["is_repo"]:
            _add(report, "Git: repository", True, f"Branch: {git['branch'] or 'detached HEAD'}", Severity.INFO)
            _add(report, "Git: remote", bool(git["remote"]), git["remote"] or "No remote configured", Severity.WARNING)
            _add(report, "Git: clean working tree", not bool(git["dirty_files"]), f"{git['dirty_files']} uncommitted file(s)" if git["dirty_files"] else "Clean", Severity.WARNING)
            _add(report, "Git LFS", True, "Available" if git["lfs_available"] else "Not installed — optional for large files", Severity.INFO)
        else:
            _add(report, "Git repository", False, "Not a git repo", Severity.WARNING)
    except Exception:
        _add(report, "Git repository", False, "Could not check", Severity.WARNING)

    if config.mode:
        _add(report, f"Project profile", True, f"Mode: {config.mode.value}", Severity.INFO)
        profile_checks = profile_service.check_profile_readiness(config, project_path)
        for pc in profile_checks:
            sev = Severity.ERROR if pc["severity"] == "error" else Severity.INFO
            _add(report, f"Profile: {pc['label']}", pc["ok"], pc["detail"], sev)
    else:
        _add(report, "Project profile", False, "No profile set — add 'mode' to .workbench/project.yaml", Severity.WARNING)

    return report


def _path_writable(path: Path) -> bool:
    probe_dir = path if path.exists() else path.parent
    if not probe_dir.exists():
        return False
    try:
        fd, probe = tempfile.mkstemp(prefix=".capsulelab-doctor-", dir=str(probe_dir))
        os.close(fd)
        Path(probe).unlink(missing_ok=True)
        return path.exists() or os.access(str(probe_dir), os.W_OK)
    except OSError:
        return False


def _add_compose_checks(report: DoctorReport, project_path: str, runtime_type: str):
    status = compose_service.status(project_path)
    compose_expected = runtime_type == "compose"
    if status["detected"]:
        _add(report, "Compose file", True, status["compose_file"] or "Detected", Severity.INFO)
        _add(
            report,
            "Compose binary",
            status["available"],
            status["binary"] or status["error"] or "Docker Compose not found",
            Severity.ERROR if compose_expected else Severity.WARNING,
        )
        if status["available"]:
            detail = f"{len(status['services'])} service(s) visible" if status["services"] else "No running services"
            _add(report, "Compose services", True, detail, Severity.INFO)
    elif compose_expected:
        _add(report, "Compose file", False, "runtime.type is compose but no compose file was found", Severity.ERROR)
    else:
        _add(report, "Compose file", True, "Not a Compose project", Severity.INFO)


def _template_identity_known(project_path: Path) -> bool:
    return _template_identity_detail(project_path) != "Unknown template source"


def _template_identity_detail(project_path: Path) -> str:
    readme = project_path / "README.md"
    config = project_path / ".workbench" / "project.yaml"
    markers = []
    for path in [readme, config]:
        if path.exists():
            text = path.read_text(errors="ignore").lower()
            for name in ["python-basic", "pytorch-cuda", "streamlit-dashboard"]:
                if name in text:
                    markers.append(name)
    if markers:
        return f"Template marker: {sorted(set(markers))[0]}"
    return "Unknown template source"
