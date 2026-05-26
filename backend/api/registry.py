from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services import registry_service

router = APIRouter()


class RegistryLoginRequest(BaseModel):
    username: str
    password: str


class ImageTagRequest(BaseModel):
    source: str
    target: str


@router.get("")
def list_registries():
    return registry_service.list_registries()


@router.get("/credentials")
def credential_status():
    return registry_service.credential_status()


@router.post("/{registry_key}/login")
def registry_login(registry_key: str, req: RegistryLoginRequest):
    try:
        result = registry_service.login(registry_key, req.username, req.password)
        if not result["ok"]:
            raise HTTPException(401, result["error"])
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{registry_key}/logout")
def registry_logout(registry_key: str):
    try:
        return registry_service.logout(registry_key)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/push")
def push_image(image: str, registry: Optional[str] = None):
    result = registry_service.push_image(image, registry)
    if not result["ok"]:
        raise HTTPException(500, result["error"])
    return result


@router.post("/pull")
def pull_image(image: str):
    result = registry_service.pull_image(image)
    if not result["ok"]:
        raise HTTPException(500, result["error"])
    return result


@router.post("/tag")
def tag_image(req: ImageTagRequest):
    result = registry_service.tag_image(req.source, req.target)
    if not result["ok"]:
        raise HTTPException(500, result["error"])
    return result
