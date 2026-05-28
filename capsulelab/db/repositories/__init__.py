from collections.abc import Callable

from .apps import AppsRepository
from .builds import BuildsRepository
from .locations import LocationsRepository
from .projects import ProjectsRepository
from .resources import ResourcesRepository
from .runs import RunsRepository
from .secrets import SecretsRepository
from .shares import SharesRepository

_db_provider: Callable | None = None


def _make_projects():
    return ProjectsRepository(_db_provider)


def _make_apps():
    return AppsRepository(_db_provider)


def _make_secrets():
    return SecretsRepository(_db_provider)


def _make_builds():
    return BuildsRepository(_db_provider)


def _make_runs():
    return RunsRepository(_db_provider)


def _make_locations():
    return LocationsRepository(_db_provider)


def _make_resources():
    return ResourcesRepository(_db_provider)


def _make_shares():
    return SharesRepository(_db_provider)


projects = _make_projects()
apps = _make_apps()
secrets = _make_secrets()
builds = _make_builds()
runs = _make_runs()
locations = _make_locations()
resources = _make_resources()
shares = _make_shares()


def configure(provider: Callable | None = None) -> None:
    """Replace all repository singletons with instances using *provider*.

    Pass ``None`` (the default) to restore the original disk-backed ``get_db``.
    Each call to ``configure()`` replaces the module-level singletons
    (``projects``, ``apps``, …), so code that imported them before a
    ``configure()`` call still holds references to the old instances.
    """
    global _db_provider, projects, apps, secrets, builds, runs, locations, resources, shares
    _db_provider = provider
    projects = _make_projects()
    apps = _make_apps()
    secrets = _make_secrets()
    builds = _make_builds()
    runs = _make_runs()
    locations = _make_locations()
    resources = _make_resources()
    shares = _make_shares()


__all__ = [
    "configure",
    "projects",
    "apps",
    "secrets",
    "builds",
    "runs",
    "locations",
    "resources",
    "shares",
]
