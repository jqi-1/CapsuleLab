from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from capsulelab.services import model_service

router = APIRouter()


class RegisterModelRequest(BaseModel):
    name: str
    version: str
    path: str
    source: str = "local"
    metadata: dict[str, Any] = {}


@router.get("")
def list_models(name: str | None = None):
    return model_service.list_models(name)


@router.post("")
def register_model(req: RegisterModelRequest):
    try:
        return model_service.register_model(req.name, req.version, req.path, req.source, req.metadata)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/{model_id}")
def get_model(model_id: str):
    model = model_service.get_model(model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    return model


@router.post("/{model_id}/verify")
def verify_model(model_id: str):
    try:
        return model_service.verify_model(model_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{model_id}")
def remove_model(model_id: str):
    if not model_service.remove_model(model_id):
        raise HTTPException(404, "Model not found")
    return {"status": "removed", "model_id": model_id}
