from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RuntimeType(str, Enum):
    docker = "docker"
    podman = "podman"
    compose = "compose"


class Mount(BaseModel):
    source: str
    target: str
    read_only: bool = False


class AppConfig(BaseModel):
    name: str
    id: str
    command: str
    port: int
    url_path: str = "/"
    healthcheck: Optional[str] = None


class RuntimeConfig(BaseModel):
    type: RuntimeType = RuntimeType.docker
    dockerfile: str = "Dockerfile"
    image: str
    gpu: bool = False


class ProjectConfig(BaseModel):
    name: str
    description: Optional[str] = None
    runtime: RuntimeConfig
    mounts: list[Mount] = Field(default_factory=lambda: [
        Mount(source=".", target="/workspace"),
    ])
    environment: dict[str, str] = Field(default_factory=dict)
    apps: list[AppConfig] = Field(default_factory=list)
