from pathlib import Path
from uuid import uuid4

from capsulelab.db.repositories import runs


def start_run(project_id: str, name: str, project_path: str, notes: str | None = None) -> dict:
    run_id = f"run-{uuid4().hex[:12]}"
    artifact_path = str(Path(project_path) / "runs" / run_id)
    Path(artifact_path).mkdir(parents=True, exist_ok=True)
    runs.create(run_id, project_id, name, notes=notes, artifact_path=artifact_path)
    return {"id": run_id, "project_id": project_id, "name": name, "status": "running", "artifact_path": artifact_path}


def finish_run(run_id: str, status: str = "finished", project_id: str | None = None):
    runs.finish(run_id, status, project_id=project_id)
    return {"id": run_id, "status": status}


def list_project_runs(project_id: str) -> list[dict]:
    return runs.list(project_id)
