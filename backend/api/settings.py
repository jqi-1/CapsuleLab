from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from capsulelab.services import settings_service

router = APIRouter()


class SetSettingRequest(BaseModel):
    value: Any


@router.get("")
def list_settings():
    return settings_service.list_settings()


@router.get("/{key:path}")
def get_setting(key: str):
    try:
        return {"key": key, "value": settings_service.get_setting(key)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{key:path}")
def set_setting(key: str, req: SetSettingRequest):
    try:
        return settings_service.set_setting(key, req.value)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{key:path}")
def remove_setting(key: str):
    return {"removed": settings_service.remove_setting(key), "key": key}
