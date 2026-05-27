from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import metadata_service

router = APIRouter()


class BackupRequest(BaseModel):
    output_path: str
    include_secrets: bool = False


class RestoreRequest(BaseModel):
    path: str
    include_secrets: bool = False


@router.post("/backup")
def create_backup(req: BackupRequest):
    try:
        return metadata_service.create_backup(req.output_path, include_secrets=req.include_secrets)
    except OSError as e:
        raise HTTPException(400, str(e))


@router.get("/backup/inspect")
def inspect_backup(path: str):
    try:
        return metadata_service.inspect_backup(path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.post("/restore")
def restore_backup(req: RestoreRequest):
    try:
        return metadata_service.restore_backup(req.path, include_secrets=req.include_secrets)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))
