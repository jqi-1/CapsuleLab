from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from backend.services import project_service, docker_service, gpu_service, app_service, compose_service, git_service, resource_service, secrets_service, build_assistant_service, ide_service
from backend.services.docker_service import parse_image_tag
from backend.db.sqlite import (
    list_projects, get_project, register_project, remove_project,
    clear_app_states, set_build_metadata, get_build_metadata,
    add_build_log, get_build_logs,
)

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


class IdeSetupRequest(BaseModel):
    ide: str


@router.get("")
def list_all_projects():
    rows = list_projects()
    enriched = []
    for row in rows:
        try:
            config = project_service.load_config(row["path"])
            container_name = project_service.get_container_name(config.name)
            running = docker_service.is_running(container_name)
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
            from backend.models.project import default_presets, ProjectMode
            pm = ProjectMode(req.mode) if req.mode in ("research", "deployable", "opensource") else None
            if pm:
                cfg_data["presets"] = default_presets(pm)
            with open(config_path, "w") as f:
                yaml.dump(cfg_data, f, default_flow_style=False)

    project_id = project_service.get_project_id(req.name)
    register_project(project_id, req.name, dest)
    return {"project_id": project_id, "name": req.name, "path": dest, "mode": req.mode}


@router.post("/import")
def import_project(req: ImportProjectRequest):
    try:
        return git_service.import_project(req.source, dest=req.path, name=req.name, scaffold=req.scaffold)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}")
def get_project_by_id(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        running = docker_service.is_running(container_name)
    except Exception:
        running = False
    return {
        **row,
        "config": config.model_dump(),
        "container_running": running,
    }


@router.delete("/{project_id}")
def delete_project(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    remove_project(project_id)
    return {"status": "removed", "project_id": project_id}


@router.post("/{project_id}/build")
def build_project(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    project_path = row["path"]
    config = project_service.load_config(project_path)
    warnings = project_service.validate(config, project_path)
    if not docker_service.check_docker():
        raise HTTPException(503, "Docker not available")
    image = config.runtime.image or f"{config.name}:dev"
    image_name, tag = parse_image_tag(image)
    try:
        result, build_logs = docker_service.build_with_logs(project_path, config.runtime.dockerfile, image_name, tag)
        add_build_log(project_id, result, "success", build_logs)
        try:
            image_info = docker_service.inspect_image(result)
            set_build_metadata(project_id, result, image_id=image_info.get("Id"), digest=",".join(image_info.get("RepoDigests", []) or []))
        except Exception:
            set_build_metadata(project_id, result)
        return {"status": "built", "image": result, "warnings": warnings, "build_logs": build_logs[:5000]}
    except docker_service.DockerError as e:
        add_build_log(project_id, image, "failed", e.stderr or str(e))
        raise HTTPException(500, {"error_code": e.error_code.value, "message": str(e), "detail": e.detail, "suggestion": e.suggestion, "logs": e.stderr or ""})
    except Exception as e:
        add_build_log(project_id, image, "failed", str(e))
        raise HTTPException(500, {"error_code": "build_failed", "message": str(e), "detail": "", "suggestion": "Check the Dockerfile and project configuration."})


@router.post("/{project_id}/start")
def start_project(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    project_path = row["path"]
    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    dkr = docker_service.check_docker_status()
    if not dkr.available:
        raise HTTPException(503, dkr.error)

    if docker_service.is_running(container_name):
        return {"status": "already_running", "container": container_name}

    if docker_service.container_exists(container_name):
        info = docker_service.inspect(container_name)
        owned = False
        if info:
            labels = info.get("Config", {}).get("Labels", {}) or {}
            owned = labels.get("com.capsulelab.project") == config.name
        if not owned:
            raise HTTPException(409,
                f"Container '{container_name}' exists but is not owned by this project."
                f" Remove it manually: docker rm -f {container_name}")
        docker_service.stop(container_name)

    clear_app_states(project_id)
    image = config.runtime.image or f"{config.name}:dev"
    mounts = []
    for m in config.mounts:
        source = str(Path(project_path) / m.source) if not Path(m.source).is_absolute() else m.source
        mounts.append((source, m.target, m.read_only))
    for c in config.caches:
        c_source = str(Path(c.source).expanduser())
        if Path(c_source).exists():
            mounts.append((c_source, c.target, True))
    for dataset in config.datasets:
        d_source = str(Path(project_path) / dataset.path) if not Path(dataset.path).is_absolute() else dataset.path
        if Path(d_source).exists():
            mounts.append((d_source, dataset.target, dataset.read_only))
    ports = [(a.port, a.port) for a in config.apps if a.port is not None] if config.apps else None

    if ports:
        used_ports = docker_service.get_used_ports()
        conflicts = [str(p[0]) for p in ports if p[0] in used_ports]
        if conflicts:
            raise HTTPException(409,
                f"Port conflict: port(s) {', '.join(conflicts)} already in use."
                f" Stop the other container or change the port mapping.")

    gpu = bool(config.runtime.gpu and gpu_service.detect_nvidia_smi())
    try:
        docker_service.run(
            container_name=container_name,
            image_name=image,
            mounts=mounts,
            env_vars=config.environment or None,
            gpu=gpu,
            ports=ports,
            labels={"com.capsulelab.project": config.name},
        )
        return {"status": "started", "container": container_name}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{project_id}/stop")
def stop_project(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)

    dkr = docker_service.check_docker_status()
    if not dkr.available:
        raise HTTPException(503, dkr.error)

    if not docker_service.container_exists(container_name):
        return {"status": "not_found", "container": container_name}

    info = docker_service.inspect(container_name)
    if info:
        labels = info.get("Config", {}).get("Labels", {}) or {}
        owned = labels.get("com.capsulelab.project") == config.name
        if not owned:
            raise HTTPException(409,
                f"Container '{container_name}' is not owned by this project."
                f" Refusing to stop.")

    try:
        docker_service.stop(container_name)
        return {"status": "stopped", "container": container_name}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{project_id}/apps")
def list_project_apps(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    return [a.model_dump() for a in config.apps]


@router.get("/{project_id}/build/logs")
def build_logs(project_id: str, limit: int = 5):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return get_build_logs(project_id, limit=limit)


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


@router.post("/{project_id}/ide/setup")
def setup_ide(project_id: str, req: IdeSetupRequest):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    try:
        return ide_service.setup_ide(row["path"], req.ide, project_name=row["name"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}/ide/{ide}/instructions")
def ide_instructions(project_id: str, ide: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    try:
        return ide_service.attach_instructions(row["path"], ide, project_name=row["name"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}/status")
def project_status(project_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    docker_status = docker_service.check_docker_status()
    running = False
    if docker_status.available:
        running = docker_service.is_running(container_name)
    gpu_info = gpu_service.get_gpu_info()
    warnings = project_service.validate(config, row["path"])
    app_statuses = [
        app_service.get_app_status(project_id, app_cfg, container_name)
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

    # Extract system and project resources for extended monitoring
    system_resources = {
        "cpu_percent": resources.get("cpu_percent"),
        "memory_used_mb": resources.get("memory_used_mb"),
        "memory_total_mb": resources.get("memory_total_mb"),
        "memory_percent": resources.get("memory_percent"),
        "disk_used_gb": resources.get("disk_used_gb"),
        "disk_total_gb": resources.get("disk_total_gb"),
        "disk_percent": resources.get("disk_percent"),
    }

    # For now, project resources are the same as system resources since we don't have container-specific monitoring yet
    # In a full implementation, this would monitor resources within the project container
    project_resources = system_resources.copy()

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
        "build": get_build_metadata(project_id),
        "git": git_status,
        "resources": resources,
        "secrets": {
            "configured": [secret.model_dump() for secret in config.secrets],
            "present": secrets_service.list_secret_presence(project_id),
            "missing": secrets_service.missing_required_secrets(project_id, config),
        },
        # Extended resource monitoring fields
        "system": system_resources,
        "project": project_resources,
    }
