from pathlib import Path

import yaml

from capsulelab.db.repositories import projects
from capsulelab.services import project_service
from capsulelab.services.git_service import GitError as GitError
from capsulelab.services.git_service import clone, is_git_url


def analyze_project(project_path: str, name: str | None = None) -> dict:
    path = Path(project_path).resolve()
    project_name = name or path.name
    compose_file = _find_first(path, ["compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"])
    dockerfile = _find_first(path, ["Dockerfile", "dockerfile"]) or path / "Dockerfile"
    package_files = _existing_names(
        path,
        [
            "requirements.txt",
            "pyproject.toml",
            "environment.yml",
            "environment.yaml",
            "Pipfile",
            "package.json",
        ],
    )
    notebook_count = len(list(path.glob("*.ipynb"))) + len(
        list((path / "notebooks").glob("*.ipynb")) if (path / "notebooks").exists() else []
    )
    apps = _detect_apps(path, package_files, notebook_count)
    gpu = _detect_gpu_intent(path, package_files, dockerfile if dockerfile.exists() else None)
    runtime_type = "compose" if compose_file else "docker"
    image = f"{project_name}:dev"
    mounts: list[dict[str, object]] = [{"source": ".", "target": "/workspace"}]
    for local_name in ["data", "datasets", "models"]:
        if (path / local_name).exists():
            mounts.append(
                {"source": f"./{local_name}", "target": f"/workspace/{local_name}", "read_only": local_name != "models"}
            )
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
            from urllib.parse import urlparse

            parsed = urlparse(source)
            dest = (
                Path(parsed.path.rstrip("/").removesuffix(".git")).name
                if parsed.path
                else Path(source.rstrip("/").removesuffix(".git")).name
            )
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
        apps.append(
            {
                "name": "Streamlit",
                "id": "streamlit",
                "command": "streamlit run app.py --server.port=8501 --server.address=0.0.0.0",
                "port": 8501,
                "url_path": "/",
            }
        )
    if "gradio" in text:
        app_file = "app.py" if (path / "app.py").exists() else "gradio_app.py"
        apps.append(
            {
                "name": "Gradio",
                "id": "gradio",
                "command": f"python {app_file}",
                "port": 7860,
                "url_path": "/",
            }
        )
    if "mlflow" in text:
        apps.append(
            {
                "name": "MLflow",
                "id": "mlflow",
                "command": "mlflow ui --host 0.0.0.0 --port 5000",
                "port": 5000,
                "url_path": "/",
            }
        )
    if "tensorboard" in text:
        apps.append(
            {
                "name": "TensorBoard",
                "id": "tensorboard",
                "command": "tensorboard --logdir runs --host 0.0.0.0 --port 6006",
                "port": 6006,
                "url_path": "/",
            }
        )
    if notebook_count or "jupyter" in text or "notebook" in text:
        apps.append(
            {
                "name": "JupyterLab",
                "id": "jupyter",
                "command": "jupyter lab --ip=0.0.0.0 --port=8899 --no-browser --allow-root --NotebookApp.token=''",
                "port": 8899,
                "url_path": "/",
            }
        )
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
