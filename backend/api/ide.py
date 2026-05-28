from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capsulelab.db.repositories import projects
from capsulelab.services import ide_service

router = APIRouter()


class IdeSetupRequest(BaseModel):
    ide: str


def _get_project(project_id: str) -> dict:
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@router.post("/{project_id}/ide/setup")
def setup_ide(project_id: str, req: IdeSetupRequest):
    row = _get_project(project_id)
    try:
        return ide_service.setup_ide(row["path"], req.ide, project_name=row["name"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}/ide/{ide}/instructions")
def ide_instructions(project_id: str, ide: str):
    row = _get_project(project_id)
    try:
        return ide_service.attach_instructions(row["path"], ide, project_name=row["name"])
    except ValueError as e:
        raise HTTPException(400, str(e))
