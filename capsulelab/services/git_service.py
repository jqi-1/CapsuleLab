import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yaml
from capsulelab.services import project_service
from capsulelab.db.repositories import projects
from capsulelab.core.errors import GitError_


class GitError(GitError_):
    pass


def _run(args: list[str], cwd: str | None = None) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise GitError("Git is not installed.") from e
    except subprocess.TimeoutExpired as e:
        raise GitError("Git command timed out.") from e
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"Git exited with code {result.returncode}")
    return result.stdout.strip()


def init_repo(project_path: str) -> dict:
    path = str(Path(project_path).resolve())
    _run(["git", "init"], cwd=path)
    try:
        _run(["git", "config", "user.name"], cwd=path)
    except GitError:
        _run(["git", "config", "user.name", "CapsuleLab"], cwd=path)
    try:
        _run(["git", "config", "user.email"], cwd=path)
    except GitError:
        _run(["git", "config", "user.email", "capsulelab@local"], cwd=path)
    _run(["git", "add", "-A"], cwd=path)
    if not _run(["git", "status", "--porcelain"], cwd=path).strip():
        return {"status": "initialized", "path": path, "commit": ""}
    _run(["git", "commit", "-m", "Initial commit"], cwd=path)
    commit_hash = _run(["git", "rev-parse", "--short", "HEAD"], cwd=path)
    return {"status": "initialized", "path": path, "commit": commit_hash}


def git_status(project_path: str) -> dict:
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_path)
    except GitError:
        return {"is_repo": False, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False}
    try:
        branch = _run(["git", "branch", "--show-current"], cwd=project_path)
        if not branch:
            branch = _run(["git", "rev-parse", "--short", "HEAD"], cwd=project_path)
        remotes = _run(["git", "remote", "-v"], cwd=project_path)
        dirty = _run(["git", "status", "--porcelain"], cwd=project_path)
    except GitError:
        return {"is_repo": True, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False}
    lfs_available = True
    try:
        _run(["git", "lfs", "version"], cwd=project_path)
    except GitError:
        lfs_available = False
    remote = remotes.splitlines()[0] if remotes else ""
    return {
        "is_repo": True,
        "branch": branch,
        "remote": remote,
        "dirty_files": len([line for line in dirty.splitlines() if line.strip()]),
        "lfs_available": lfs_available,
    }


def ensure_repo(project_path: str) -> None:
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_path)
    except GitError as e:
        raise GitError(f"Not a git repository: {project_path}") from e


def history(project_path: str, limit: int = 10) -> list[dict]:
    ensure_repo(project_path)
    raw = _run(["git", "log", f"--max-count={limit}", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"], cwd=project_path)
    commits = []
    for line in raw.splitlines():
        parts = line.split("\t", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return commits


def branches(project_path: str) -> dict:
    ensure_repo(project_path)
    raw = _run(["git", "branch", "--list"], cwd=project_path)
    items = []
    current = ""
    for line in raw.splitlines():
        name = line.strip()
        active = name.startswith("* ")
        if active:
            name = name[2:]
            current = name
        items.append({"name": name, "current": active})
    return {"current": current, "branches": items}


def switch_branch(project_path: str, branch: str, create: bool = False) -> dict:
    ensure_repo(project_path)
    args = ["git", "switch"]
    if create:
        args.append("-c")
    args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "switched", "branch": branch, "output": output}


def fetch(project_path: str, remote: str = "origin") -> dict:
    ensure_repo(project_path)
    output = _run(["git", "fetch", remote], cwd=project_path)
    return {"status": "fetched", "remote": remote, "output": output}


def pull(project_path: str, remote: str = "origin", branch: str | None = None) -> dict:
    ensure_repo(project_path)
    args = ["git", "pull", remote]
    if branch:
        args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "pulled", "remote": remote, "branch": branch, "output": output}


def push(project_path: str, remote: str = "origin", branch: str | None = None, set_upstream: bool = False) -> dict:
    ensure_repo(project_path)
    args = ["git", "push"]
    if set_upstream:
        args.append("-u")
    args.append(remote)
    if branch:
        args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "pushed", "remote": remote, "branch": branch, "output": output}


def commit(project_path: str, message: str, all_changes: bool = True) -> dict:
    ensure_repo(project_path)
    if all_changes:
        _run(["git", "add", "-A"], cwd=project_path)
    if not _run(["git", "status", "--porcelain"], cwd=project_path).strip():
        return {"status": "clean", "commit": "", "output": "No changes to commit"}
    output = _run(["git", "commit", "-m", message], cwd=project_path)
    commit_hash = _run(["git", "rev-parse", "--short", "HEAD"], cwd=project_path)
    return {"status": "committed", "commit": commit_hash, "output": output}


def add_remote(project_path: str, remote: str, url: str) -> dict:
    ensure_repo(project_path)
    remotes = _run(["git", "remote"], cwd=project_path).splitlines()
    if remote in remotes:
        _run(["git", "remote", "set-url", remote, url], cwd=project_path)
        return {"status": "updated", "remote": remote, "url": url}
    _run(["git", "remote", "add", remote, url], cwd=project_path)
    return {"status": "added", "remote": remote, "url": url}


def publish(project_path: str, remote_url: str, remote: str = "origin", branch: str | None = None) -> dict:
    ensure_repo(project_path)
    add_remote(project_path, remote, remote_url)
    if not branch:
        branch = _run(["git", "branch", "--show-current"], cwd=project_path) or "main"
    pushed = push(project_path, remote=remote, branch=branch, set_upstream=True)
    return {"status": "published", "remote": remote, "url": remote_url, "branch": branch, "push": pushed}


def clone(url: str, dest: str) -> str:
    _run(["git", "clone", url, dest])
    return dest


def is_git_url(source: str) -> bool:
    parsed = urlparse(source)
    return (
        parsed.scheme in {"http", "https", "ssh", "git"}
        or source.startswith("git@")
        or source.endswith(".git")
    )


def analyze_project(project_path: str, name: str | None = None) -> dict:
    path = Path(project_path).resolve()
    project_name = name or path.name
    compose_file = _find_first(path, ["compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"])
    dockerfile = _find_first(path, ["Dockerfile", "dockerfile"]) or path / "Dockerfile"
    package_files = _existing_names(path, [
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "Pipfile",
        "package.json",
    ])
    notebook_count = len(list(path.glob("*.ipynb"))) + len(list((path / "notebooks").glob("*.ipynb")) if (path / "notebooks").exists() else [])
    apps = _detect_apps(path, package_files, notebook_count)
    gpu = _detect_gpu_intent(path, package_files, dockerfile if dockerfile.exists() else None)
    runtime_type = "compose" if compose_file else "docker"
    image = f"{project_name}:dev"
    mounts = [{"source": ".", "target": "/workspace"}]
    for local_name in ["data", "datasets", "models"]:
        if (path / local_name).exists():
            mounts.append({"source": f"./{local_name}", "target": f"/workspace/{local_name}", "read_only": local_name != "models"})
    return {
        "name": project_name,
        "runtime": {
            "type": runtime_type,
            "dockerfile": str(dockerfile.relative_to(path)) if dockerfile.exists() else "Dockerfile",
            "image": image,
            "gpu": gpu,
        },
        "mounts": mounts,
        "environment": {"PYTHONPATH": "/workspace"},
        "apps": apps,
        "detected": {
            "compose_file": str(compose_file.relative_to(path)) if compose_file else None,
            "dockerfile": str(dockerfile.relative_to(path)) if dockerfile.exists() else None,
            "package_files": package_files,
            "notebook_count": notebook_count,
            "gpu_intent": gpu,
            "app_ids": [app["id"] for app in apps],
        },
    }


def ensure_config(project_path: str, name: str | None = None, image: str | None = None) -> str:
    path = Path(project_path)
    config_path = path / project_service.WORKBENCH_DIR / project_service.CONFIG_FILE
    if config_path.exists():
        return str(config_path)
    detected = analyze_project(str(path), name=name)
    if image:
        detected["runtime"]["image"] = image
    (path / project_service.WORKBENCH_DIR).mkdir(parents=True, exist_ok=True)
    config_data = {k: v for k, v in detected.items() if k != "detected"}
    config_path.write_text(yaml.safe_dump(config_data, sort_keys=False))
    return str(config_path)


def register_existing(project_path: str, name: str | None = None, scaffold: bool = True) -> dict:
    path = Path(project_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Project path not found: {path}")
    project_name = name or path.name
    if scaffold:
        ensure_config(str(path), project_name)
    config = project_service.load_config(str(path))
    project_id = project_service.get_project_id(config.name)
    projects.register(project_id, config.name, str(path))
    return {
        "project_id": project_id,
        "name": config.name,
        "path": str(path),
        "detected": analyze_project(str(path), name=config.name)["detected"],
    }


def import_project(source: str, dest: str | None = None, name: str | None = None, scaffold: bool = True) -> dict:
    if is_git_url(source):
        if not dest:
            dest = Path(source.rstrip("/").removesuffix(".git")).name
        clone(source, dest)
        return register_existing(dest, name=name, scaffold=scaffold)
    return register_existing(source, name=name, scaffold=scaffold)


def repair_inventory(base_dir: str) -> list[dict]:
    repaired: list[dict] = []
    for project in project_service.find_projects(base_dir):
        project_id = project_service.get_project_id(project["name"])
        projects.register(project_id, project["name"], str(project["path"]))
        repaired.append({"project_id": project_id, "name": project["name"], "path": str(project["path"])})
    return repaired


def inventory() -> list[dict]:
    return projects.list()


def _find_first(path: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = path / name
        if candidate.exists():
            return candidate
    for name in names:
        matches = list(path.glob(f"*/{name}"))
        if matches:
            return matches[0]
    return None


def _existing_names(path: Path, names: list[str]) -> list[str]:
    return [name for name in names if (path / name).exists()]


def _read_project_text(path: Path, package_files: list[str], dockerfile: Path | None) -> str:
    chunks = []
    for name in package_files:
        try:
            chunks.append((path / name).read_text(errors="ignore"))
        except OSError:
            pass
    if dockerfile:
        try:
            chunks.append(dockerfile.read_text(errors="ignore"))
        except OSError:
            pass
    return "\n".join(chunks).lower()


def _detect_gpu_intent(path: Path, package_files: list[str], dockerfile: Path | None) -> bool:
    text = _read_project_text(path, package_files, dockerfile)
    gpu_markers = ["cuda", "nvidia", "cudnn", "cupy", "tensorflow-gpu", "pytorch/pytorch", "torch==", "torch>="]
    return any(marker in text for marker in gpu_markers)


def _detect_apps(path: Path, package_files: list[str], notebook_count: int) -> list[dict]:
    text = _read_project_text(path, package_files, None)
    apps: list[dict] = []
    if (path / "app.py").exists() and "streamlit" in text:
        apps.append({
            "name": "Streamlit",
            "id": "streamlit",
            "command": "streamlit run app.py --server.port=8501 --server.address=0.0.0.0",
            "port": 8501,
            "url_path": "/",
        })
    if "gradio" in text:
        app_file = "app.py" if (path / "app.py").exists() else "gradio_app.py"
        apps.append({
            "name": "Gradio",
            "id": "gradio",
            "command": f"python {app_file}",
            "port": 7860,
            "url_path": "/",
        })
    if "mlflow" in text:
        apps.append({
            "name": "MLflow",
            "id": "mlflow",
            "command": "mlflow ui --host 0.0.0.0 --port 5000",
            "port": 5000,
            "url_path": "/",
        })
    if "tensorboard" in text:
        apps.append({
            "name": "TensorBoard",
            "id": "tensorboard",
            "command": "tensorboard --logdir runs --host 0.0.0.0 --port 6006",
            "port": 6006,
            "url_path": "/",
        })
    if notebook_count or "jupyter" in text or "notebook" in text:
        apps.append({
            "name": "JupyterLab",
            "id": "jupyter",
            "command": "jupyter lab --ip=0.0.0.0 --port=8899 --no-browser --allow-root --NotebookApp.token=''",
            "port": 8899,
            "url_path": "/",
        })
    return _dedupe_apps(apps)


def _dedupe_apps(apps: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for app in apps:
        if app["id"] in seen:
            continue
        seen.add(app["id"])
        unique.append(app)
    return unique
