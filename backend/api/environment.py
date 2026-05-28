from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capsulelab.db.repositories import projects
from capsulelab.services import environment_service

router = APIRouter()


class AddDependencyRequest(BaseModel):
    dependency: str


class EnvironmentVariableRequest(BaseModel):
    name: str
    value: str


def _get_project(project_id: str) -> dict:
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@router.get("/{project_id}/environment")
def project_environment(project_id: str):
    row = _get_project(project_id)
    try:
        return environment_service.describe(row["path"])
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/{project_id}/environment/dependencies")
def add_project_dependency(project_id: str, req: AddDependencyRequest):
    row = _get_project(project_id)
    try:
        return environment_service.add_dependency(row["path"], req.dependency)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{project_id}/environment/variables")
def set_project_environment_variable(project_id: str, req: EnvironmentVariableRequest):
    row = _get_project(project_id)
    try:
        return environment_service.set_environment_variable(row["path"], req.name, req.value)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.delete("/{project_id}/environment/variables/{name}")
def remove_project_environment_variable(project_id: str, name: str):
    row = _get_project(project_id)
    try:
        return environment_service.remove_environment_variable(row["path"], name)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
