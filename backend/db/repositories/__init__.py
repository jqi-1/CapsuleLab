from .projects import ProjectsRepository
from .apps import AppsRepository
from .secrets import SecretsRepository
from .builds import BuildsRepository
from .runs import RunsRepository
from .locations import LocationsRepository
from .resources import ResourcesRepository
from .shares import SharesRepository

projects = ProjectsRepository()
apps = AppsRepository()
secrets = SecretsRepository()
builds = BuildsRepository()
runs = RunsRepository()
locations = LocationsRepository()
resources = ResourcesRepository()
shares = SharesRepository()

__all__ = [
    "projects",
    "apps",
    "secrets",
    "builds",
    "runs",
    "locations",
    "resources",
    "shares",
]
