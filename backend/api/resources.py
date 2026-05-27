from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from capsulelab.db.repositories import projects
from capsulelab.services import resource_service

router = APIRouter()


def _project(project_id: str):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@router.get("/{project_id}/resources/current")
def get_current_resources(project_id: str):
    """Get current resource usage for a project"""
    row = _project(project_id)
    # Get system resources (simplified - in reality would monitor the project container)
    system_resources = resource_service.get_system_resources()

    # Get project-specific disk usage
    project_resources = resource_service.project_resources(row["path"])

    return {
        "project_id": project_id,
        "system": system_resources,
        "project": project_resources,
        "timestamp": resource_service.get_current_timestamp()
    }


@router.get("/{project_id}/resources/history")
def get_resource_history(
    project_id: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get historical resource usage for a project"""
    row = _project(project_id)
    history = resource_service.get_resource_history(project_id, limit)
    return {
        "project_id": project_id,
        "history": history,
        "count": len(history)
    }


@router.get("/{project_id}/resources/snapshot")
def get_latest_resource_snapshot(project_id: str):
    """Get the most recent resource snapshot for a project"""
    row = _project(project_id)
    snapshot = resource_service.get_latest_resource_snapshot(project_id)
    if not snapshot:
        raise HTTPException(404, "No resource snapshots found for project")
    return {
        "project_id": project_id,
        "snapshot": snapshot
    }


@router.post("/{project_id}/resources/collect")
def collect_resource_snapshot(project_id: str):
    """Manually trigger collection of a resource snapshot"""
    row = _project(project_id)
    # Get current resources
    system_resources = resource_service.get_system_resources()
    project_resources = resource_service.project_resources(row["path"])

    # Combine resources
    combined_resources = {
        **system_resources,
        **project_resources
    }

    # Store snapshot
    snapshot_id = resource_service.store_resource_snapshot(project_id, combined_resources)

    return {
        "project_id": project_id,
        "snapshot_id": snapshot_id,
        "message": "Resource snapshot collected successfully"
    }