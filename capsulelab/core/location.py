from typing import Optional

from pydantic import BaseModel


class Location(BaseModel):
    name: str
    type: str = "local"
    host: Optional[str] = None
    user: Optional[str] = None
    project_root: Optional[str] = None
    runtime: str = "docker"
    gpu: bool = False
