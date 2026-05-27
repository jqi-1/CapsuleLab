from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.sqlite import init_db
from backend.api import projects, apps, logs, compose, locations, backlog, resources, registry, models, metadata, settings
from backend.services import docker_service, gpu_service

app = FastAPI(title="CapsuleLab API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(apps.router, prefix="/api/projects/{project_id}/apps", tags=["apps"])
app.include_router(logs.router, prefix="/api/projects/{project_id}", tags=["logs"])
app.include_router(compose.router, prefix="/api/projects/{project_id}", tags=["compose"])
app.include_router(backlog.router, prefix="/api/projects/{project_id}", tags=["project-meta"])
app.include_router(locations.router, prefix="/api/locations", tags=["locations"])
app.include_router(resources.router, prefix="/api/projects", tags=["resources"])
app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(metadata.router, prefix="/api/metadata", tags=["metadata"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/profiles")
def list_profiles():
    from backend.services import profile_service
    return profile_service.list_profiles()


@app.get("/api/doctor")
def doctor():
    dkr = docker_service.check_docker_status()
    gpu = gpu_service.get_gpu_info()
    return {
        "docker": {
            "available": dkr.available,
            "binary_found": dkr.binary_found,
            "daemon_running": dkr.daemon_running,
            "socket_accessible": dkr.socket_accessible,
            "version": dkr.version,
            "error": dkr.error,
        },
        "gpu": {
            "available": gpu.available,
            "name": gpu.name,
            "vram_mb": gpu.vram_mb,
        },
    }
