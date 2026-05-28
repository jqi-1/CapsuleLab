from capsulelab.db.repositories import configure
from capsulelab.db.testing import in_memory_db_provider


def test_configure_with_in_memory_isolation():
    import capsulelab.db.repositories as repos

    p1 = in_memory_db_provider()
    configure(p1)
    repos.projects.register("proj-1", "Project 1", "/tmp/p1")

    p2 = in_memory_db_provider()
    configure(p2)
    repos.projects.register("proj-2", "Project 2", "/tmp/p2")

    configure(p1)
    rows = repos.projects.list()
    ids = [r["id"] for r in rows]
    assert "proj-1" in ids
    assert "proj-2" not in ids, "proj-2 leaked across isolated databases"


def test_configure_resets_projects():
    import capsulelab.db.repositories as repos

    provider = in_memory_db_provider()
    configure(provider)
    repos.projects.register("proj-1", "P1", "/tmp/p1")
    assert repos.projects.get("proj-1") is not None

    configure(in_memory_db_provider())
    assert repos.projects.get("proj-1") is None


def test_configure_affects_all_repos():
    import capsulelab.db.repositories as repos

    provider = in_memory_db_provider()
    configure(provider)

    repos.projects.register("proj-1", "P1", "/tmp/p1")
    repos.apps.set_state("proj-1", "jupyter", "running", pid=123)

    state = repos.apps.get_state("proj-1", "jupyter")
    assert state is not None
    assert state["pid"] == 123
