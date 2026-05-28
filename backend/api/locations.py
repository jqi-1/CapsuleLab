from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capsulelab.db.repositories import locations
from capsulelab.services import ssh_service

router = APIRouter()


class CreateLocationRequest(BaseModel):
    name: str
    host: str
    user: Optional[str] = None
    project_root: Optional[str] = None
    runtime: str = "docker"
    gpu: bool = False


class UpdateLocationRequest(BaseModel):
    host: Optional[str] = None
    user: Optional[str] = None
    project_root: Optional[str] = None
    runtime: Optional[str] = None
    gpu: Optional[bool] = None


@router.get("")
def list_all_locations():
    return locations.list()


@router.post("")
def create_location(req: CreateLocationRequest):
    existing = locations.get_by_name(req.name)
    if existing:
        raise HTTPException(409, f"Location '{req.name}' already exists")
    from uuid import uuid4

    location_id = str(uuid4())
    locations.register(location_id, req.name, "ssh", req.host, req.user, req.project_root, req.runtime, req.gpu)
    loc = locations.get_by_name(req.name)
    if loc:
        ssh_service.assign_tunnel_ports(loc["id"])
    return loc or {"id": location_id, "name": req.name}


@router.delete("/{name}")
def delete_location(name: str):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    locations.remove(loc["id"])
    return {"status": "removed", "name": name}


@router.get("/{name}/status")
def location_status(name: str):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    status = ssh_service.check_status(loc["host"], loc["user"], loc.get("project_root"))
    return {
        "name": loc["name"],
        "host": loc["host"],
        "user": loc["user"],
        "project_root": loc["project_root"],
        "gpu_configured": bool(loc["gpu"]),
        "reachable": status.reachable,
        "docker_available": status.docker_available,
        "docker_version": status.docker_version,
        "gpu_available": status.gpu_available,
        "gpu_name": status.gpu_name,
        "project_root_exists": status.project_path_exists,
        "disk_total_gb": status.disk_total_gb,
        "disk_free_gb": status.disk_free_gb,
        "disk_used_percent": status.disk_used_percent,
        "error": status.error,
        "tunnel": ssh_service.tunnel_info(loc),
    }


@router.get("/{name}/tunnel")
def location_tunnel(name: str):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    return ssh_service.tunnel_info(loc)


class SetOverrideRequest(BaseModel):
    override_type: str
    logical_name: str
    value: str


class SetOverrideResponse(BaseModel):
    location: str
    override_type: str
    logical_name: str
    value: str


@router.post("/{name}/overrides")
def add_location_override(name: str, req: SetOverrideRequest):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    if req.override_type not in ("dataset", "cache", "secret"):
        raise HTTPException(400, "override_type must be 'dataset', 'cache', or 'secret'")
    locations.set_override(loc["id"], req.override_type, req.logical_name, req.value)
    return SetOverrideResponse(
        location=name, override_type=req.override_type, logical_name=req.logical_name, value=req.value
    )


@router.delete("/{name}/overrides/{override_type}/{logical_name}")
def remove_location_override_endpoint(name: str, override_type: str, logical_name: str):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    locations.remove_override(loc["id"], override_type, logical_name)
    return {"status": "removed", "location": name, "override_type": override_type, "logical_name": logical_name}


@router.get("/{name}/overrides")
def get_location_overrides(name: str):
    loc = locations.get_by_name(name)
    if not loc:
        raise HTTPException(404, "Location not found")
    return locations.list_overrides(loc["id"])
