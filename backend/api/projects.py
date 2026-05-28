from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capsulelab.db.repositories import apps, builds, projects
from capsulelab.services import (
    app_service,
    build_assistant_service,
    compose_service,
    docker_service,
    git_service,
    gpu_service,
    project_import_service,
    project_service,
    resource_service,
    runtime_service,
    secrets_service,
)
from capsulelab.services.docker_service import parse_image_tag

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    template: str = "python-basic"
    path: Optional[str] = None
    mode: Optional[str] = None


class ImportProjectRequest(BaseModel):
    source: str
    path: Optional[str] = None
    name: Optional[str] = None
    scaffold: bool = True


def _get_project(project_id: str) -> dict:
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@router.get("")
def list_all_projects():
    rows = projects.list()
    enriched = []
    for row in rows:
        try:
            config = project_service.load_config(row["path"])
            runtime = runtime_service.RuntimeManager(runtime_service.LocalDockerAdapter())
            running = runtime.status(project_service.get_container_name(config.name)).running
        except Exception:
            running = False
        enriched.append({**row, "container_running": running})
    return enriched


@router.post("")
def create_project(req: CreateProjectRequest):
    templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    template_path = templates_dir / req.template
    if not template_path.exists():
        raise HTTPException(400, f"Template '{req.template}' not found")
    dest = req.path or str(Path.cwd() / req.name)
    try:
        project_service.create_from_template(req.name, str(template_path), dest)
    except FileExistsError as e:
        raise HTTPException(409, str(e))

    if req.mode:
        import yaml

        config_path = Path(dest) / ".workbench" / "project.yaml"
        if config_path.exists():
            with open(config_path) as f:
                cfg_data = yaml.safe_load(f)
            cfg_data["mode"] = req.mode
            from capsulelab.core.project import ProjectMode, default_presets

            pm = ProjectMode(req.mode) if req.mode in ("research", "deployable", "opensource") else None
            if pm:
                cfg_data["presets"] = default_presets(pm)
            with open(config_path, "w") as f:
                yaml.dump(cfg_data, f, default_flow_style=False)

    project_id = project_service.get_project_id(req.name)
    projects.register(project_id, req.name, dest)
    return {"project_id": project_id, "name": req.name, "path": dest, "mode": req.mode}


@router.post("/import")
def import_project(req: ImportProjectRequest):
    try:
        return project_import_service.import_project(req.source, dest=req.path, name=req.name, scaffold=req.scaffold)

    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except (git_service.GitError, project_import_service.GitError) as e:
        raise HTTPException(400, e.to_dict())
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}")
def get_project_by_id(project_id: str):
    row = _get_project(project_id)
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        runtime = runtime_service.RuntimeManager(runtime_service.LocalDockerAdapter())
        running = runtime.status(container_name).running
    except Exception:
        running = False
    return {
        **row,
        "config": config.model_dump(),
        "container_running": running,
    }


@router.delete("/{project_id}")
def delete_project(project_id: str):
    _get_project(project_id)
    projects.remove(project_id)
    return {"status": "removed", "project_id": project_id}


@router.post("/{project_id}/build")
def build_project(project_id: str):
    row = _get_project(project_id)
    project_path = row["path"]
    config = project_service.load_config(project_path)
    warnings = project_service.validate(config, project_path)
    if not docker_service.check_docker():
        raise HTTPException(503, "Docker not available")
    image = config.runtime.image or f"{config.name}:dev"
    image_name, tag = parse_image_tag(image)
    try:
        result, build_logs = docker_service.build_with_logs(project_path, config.runtime.dockerfile, image_name, tag)
        builds.add_log(project_id, result, "success", build_logs)
        try:
            image_info = docker_service.inspect_image(result)
            builds.set_metadata(
                project_id,
                result,
                image_id=image_info.get("Id"),
                digest=",".join(image_info.get("RepoDigests", []) or []),
            )
        except Exception:
            builds.set_metadata(project_id, result)
        return {"status": "built", "image": result, "warnings": warnings, "build_logs": build_logs[:5000]}
    except docker_service.DockerError as e:
        builds.add_log(project_id, image, "failed", e.stderr or str(e))
        raise HTTPException(
            500,
            {
                "error_code": e.error_code.value,
                "message": str(e),
                "detail": e.detail,
                "suggestion": e.suggestion,
                "logs": e.stderr or "",
            },
        )
    except Exception as e:
        builds.add_log(project_id, image, "failed", str(e))
        raise HTTPException(
            500,
            {
                "error_code": "build_failed",
                "message": str(e),
                "detail": "",
                "suggestion": "Check the Dockerfile and project configuration.",
            },
        )


@router.post("/{project_id}/start")
def start_project(project_id: str):
    row = _get_project(project_id)
    project_path = row["path"]
    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)
    try:
        runtime = runtime_service.RuntimeManager(runtime_service.LocalDockerAdapter())
        result = runtime.start(project_path, config, container_name)
        if result.status == "started":
            apps.clear_states(project_id)
        return {"status": result.status, "container": result.container}
    except runtime_service.RuntimeUnavailable as e:
        raise HTTPException(503, str(e))
    except runtime_service.RuntimeConflict as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{project_id}/stop")
def stop_project(project_id: str):
    row = _get_project(project_id)
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        runtime = runtime_service.RuntimeManager(runtime_service.LocalDockerAdapter())
        result = runtime.stop(config, container_name)
        return {"status": result.status, "container": result.container}
    except runtime_service.RuntimeUnavailable as e:
        raise HTTPException(503, str(e))
    except runtime_service.RuntimeConflict as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{project_id}/apps")
def list_project_apps(project_id: str):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    return [a.model_dump() for a in config.apps]


@router.get("/{project_id}/build/logs")
def build_logs(project_id: str, limit: int = 5):
    _get_project(project_id)
    return builds.get_logs(project_id, limit=limit)


@router.get("/{project_id}/build/assistant")
def build_assistant(project_id: str):
    try:
        return build_assistant_service.analyze_failed_build(project_id).to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{project_id}/build/assistant/apply")
def apply_build_assistant(project_id: str):
    try:
        return build_assistant_service.apply_first_proposed_edit(project_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


def _resource_slice(resources: dict) -> dict:
    keys = [
        "cpu_percent",
        "memory_used_mb",
        "memory_total_mb",
        "memory_percent",
        "disk_used_gb",
        "disk_total_gb",
        "disk_percent",
    ]
    return {k: resources.get(k) for k in keys}


@router.get("/{project_id}/status")
def project_status(project_id: str):
    row = _get_project(project_id)
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    runtime = runtime_service.RuntimeManager(runtime_service.LocalDockerAdapter())
    runtime_status = runtime.status(container_name)
    docker_status = runtime_status.health
    running = runtime_status.running
    gpu_info = gpu_service.get_gpu_info()
    warnings = project_service.validate(config, row["path"])
    app_statuses = [
        app_service.get_app_status(runtime_service.LocalDockerAdapter(), project_id, app_cfg, container_name)
        for app_cfg in config.apps
    ]

    try:
        git_status = git_service.git_status(row["path"])
    except Exception:
        git_status = {"is_repo": False, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False}

    try:
        resources = resource_service.project_resources(row["path"])
    except Exception:
        resources = {
            "disk": {"path": row["path"], "total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "free_percent": 0},
            "gpu": {"available": False, "gpus": []},
        }

    system_resources = _resource_slice(resources)
    project_resources = _resource_slice(resources)

    return {
        "name": config.name,
        "project_id": project_id,
        "container": container_name,
        "container_running": running,
        "docker": {
            "available": docker_status.available,
            "binary_found": docker_status.binary_found,
            "daemon_running": docker_status.daemon_running,
            "socket_accessible": docker_status.socket_accessible,
            "version": docker_status.version,
            "error": docker_status.error,
        },
        "gpu_available": gpu_info.available,
        "gpu_name": gpu_info.name,
        "gpu_vram_mb": gpu_info.vram_mb,
        "readiness": {
            "ok": docker_status.available and not warnings,
            "warnings": warnings,
        },
        "apps": app_statuses,
        "compose": compose_service.status(row["path"]),
        "build": builds.get_metadata(project_id),
        "git": git_status,
        "resources": resources,
        "secrets": {
            "configured": [secret.model_dump() for secret in config.secrets],
            "present": secrets_service.list_secret_presence(project_id),
            "missing": secrets_service.missing_required_secrets(project_id, config),
        },
        "system": system_resources,
        "project": project_resources,
    }
