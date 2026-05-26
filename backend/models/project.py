from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RuntimeType(str, Enum):
    docker = "docker"
    podman = "podman"
    compose = "compose"


class ProjectMode(str, Enum):
    research = "research"
    deployable = "deployable"
    opensource = "opensource"


RESEARCH_PRESETS = {
    "notebook_first": True,
    "experiment_tracking": True,
    "dataset_mounts": True,
    "model_cache": True,
    "knowledge_graph": True,
    "paper_notes": True,
    "reproducibility_checks": True,
}

DEPLOYABLE_PRESETS = {
    "api_server": True,
    "dockerfile_required": True,
    "health_checks": True,
    "env_validation": True,
    "tests_required": True,
    "secrets_scan": True,
    "deployment_manifest": True,
    "logging_dashboard": True,
}

OPENSOURCE_PRESETS = {
    "readme_required": True,
    "license_required": True,
    "contributing_required": True,
    "tests_required": True,
    "examples_required": True,
    "github_actions": True,
    "docs_preview": True,
    "package_metadata_check": True,
}


def default_presets(mode: ProjectMode | None) -> dict[str, bool]:
    if mode == ProjectMode.research:
        return dict(RESEARCH_PRESETS)
    elif mode == ProjectMode.deployable:
        return dict(DEPLOYABLE_PRESETS)
    elif mode == ProjectMode.opensource:
        return dict(OPENSOURCE_PRESETS)
    return {}


class Mount(BaseModel):
    source: str
    target: str
    read_only: bool = False


class Cache(BaseModel):
    source: str
    target: str


class Dataset(BaseModel):
    name: str
    path: str
    target: str
    read_only: bool = True


class SecretRef(BaseModel):
    name: str
    location: Optional[str] = None
    required: bool = True


class AppConfig(BaseModel):
    name: str
    id: str
    command: str
    port: Optional[int] = None
    url_path: str = "/"
    healthcheck: Optional[str] = None
    kind: str = "web"


class RuntimeConfig(BaseModel):
    type: RuntimeType = RuntimeType.docker
    dockerfile: str = "Dockerfile"
    image: str
    gpu: bool = False


class ProjectConfig(BaseModel):
    name: str
    description: Optional[str] = None
    mode: Optional[ProjectMode] = None
    presets: dict[str, bool] = Field(default_factory=dict)
    runtime: RuntimeConfig
    mounts: list[Mount] = Field(default_factory=lambda: [
        Mount(source=".", target="/workspace"),
    ])
    caches: list[Cache] = Field(default_factory=lambda: [
        Cache(source="~/.cache/huggingface", target="/root/.cache/huggingface"),
        Cache(source="~/.cache/torch", target="/root/.cache/torch"),
    ])
    datasets: list[Dataset] = Field(default_factory=list)
    secrets: list[SecretRef] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    apps: list[AppConfig] = Field(default_factory=list)
