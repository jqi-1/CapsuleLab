# Deepening Opportunities

Record of architectural candidates surfaced during the 2026-05-28 architecture review.
Each candidate is a **deepening opportunity** — a refactor that turns a shallow module into a deeper one,
improving testability and AI-navigability.

---

## Candidate 1: App lifecycle bypasses the RuntimeAdapter seam

**Files:** `capsulelab/services/app_service.py`, `capsulelab/services/runtime_service.py`,
`cli/commands/app.py`, `backend/api/apps.py`

**Problem:** The `RuntimeAdapter` protocol + `RuntimeManager` exist (ADR-0001) and define the seam
for testable container lifecycle. ADR-0001 says *"All start/stop/status entry points must go through
RuntimeManager."* But `app_service.start_app()` / `stop_app()` / `get_app_status()` call
`docker_service.exec_run()`, `docker_service.is_running()`, and even `socket.socket()` directly —
bypassing the adapter entirely. Remote app management therefore requires a completely different
pathway, and tests must monkeypatch `docker_service` globals instead of injecting a fake adapter.

**Solution:** Add `exec_run` and `app_log_path` to the `RuntimeAdapter` protocol. Move app
lifecycle into `RuntimeManager` (or an `AppManager` sibling that also accepts a `RuntimeAdapter`).
`app_service` becomes a **shallower** module — just pre-flight logic (config lookup, command
construction, URL/port mapping) — delegating all container-touching operations through the adapter.

**Benefits:**
- **Leverage:** One seam for all container operations (project + app lifecycle), not two.
- **Locality:** Bugs in port-conflict detection, alive checks, and process termination concentrate
  behind the adapter instead of being scattered across `app_service` and `runtime_service`.
- **Tests:** Injects `FakeAdapter` for app lifecycle tests — no Docker daemon, no module-global
  monkeypatching.
- **ADR compliance:** Brings the codebase into alignment with ADR-0001.

---

## Candidate 2: Doctor is a hyper-coupled crawler, not a deep module

**Files:** `capsulelab/services/doctor_service.py`, 8+ imported service modules

**Problem:** `doctor_service.py` is a 303-line module whose interface
(`project_doctor_for_path(project_id) -> DoctorReport`) looks deep but is a lie. The implementation
is a flat 180-line sequential check that reaches into the internals of 8+ services
(`docker_service`, `gpu_service`, `git_service`, `image_service`, `compose_service`,
`profile_service`, `project_service`, `secrets_service`). A change in any of those can break
doctor. Tests monkeypatch `doctor_service.docker_service.*` references — fragile and coupled to
import paths.

The deletion test: doctor *does* concentrate complexity (passes), but at a coupling cost that makes
it brittle. The interface promises simplicity but the implementation has no seam to test in
isolation.

**Solution:** Define a `HealthCheckable` protocol. Each service that has health signals exposes a
`check_health(project_id, project_path, config) -> list[DoctorCheck]` function. `doctor_service`
becomes a pure aggregator: it iterates registered checkables, collects their checks, and flattens
them into a report. Inline checks (config loading, package manifests, app config, mounts) stay
in doctor since they have no natural home.

**Benefits:**
- **Leverage:** Adding a new service means implementing one function in that service, not adding
  an import + 20-line block to doctor.
- **Locality:** A broken check lives beside the code it checks — fixes don't bounce between two
  files. A change to `docker_service` changes only `docker_service.check_health()`, not doctor.
- **Tests:** Test each service's `check_health()` in the service's own test file with focused
  fixtures. Test doctor as an aggregator with fake checkables — 10 lines, zero monkeypatching.

---

## Candidate 3: `git_service.py` mixes three concerns behind one name

**Files:** `capsulelab/services/git_service.py` (379 lines)

**Problem:** This single module does three distinct things behind one name:
1. **Git operations** — `clone`, `commit`, `push`, `pull`, `branches`, `history`,
   `switch_branch`, `fetch`.
2. **Project import / detection** — `import_project`, `analyze_project`, `ensure_config`,
   `register_existing`, `repair_inventory`, `inventory`.
3. **App detection from package files** — `_detect_apps`, `_detect_gpu_intent`.

These have different change frequencies, test requirements, and domain concepts. Understanding
"how does project import work" requires tracing through git operations → project detection →
persistence — all in one file. The module is **shallow** because its interface is nearly as broad
as its implementation: five public functions, five different responsibilities.

**Solution:** Split into three modules:
- `capsulelab/services/git_service.py` — pure git operations only (clone, commit, push, pull,
  branches, history, switch_branch, fetch, init_repo).
- `capsulelab/services/project_import_service.py` — import, inventory, repair, registration,
  detection.
- Detection heuristics move inline into each template or into `capsulelab/core/detection.py`.

**Benefits:**
- **Locality:** Change the import flow without touching a git command. Change a detection
  heuristic without risking a push command.
- **Leverage:** Each module has a focused interface instead of one broad one.
- **Tests:** Git operations tested with a fake git repo. Import logic tested with a filesystem
  fixture. Detection tested with a known set of package files. No overlap.

---

## Candidate 4: `resource_service.py` bypasses its own repository and writes raw SQL

**Files:** `capsulelab/services/resource_service.py`, `capsulelab/db/repositories/resources.py`

**Problem:** CONTEXT.md says *"No direct SQLite imports outside repositories."* `resource_service.py`
violates this — it imports `get_db` from `capsulelab.db.sqlite` and writes
`INSERT INTO resource_snapshots` directly, duplicating the exact same operations that live in
`ResourcesRepository`. The service is also **untested** — no `test_resource_service.py` exists.
`ResourcesRepository` has a `db_provider=None` injection seam designed for testability, but it's
never used because the service doesn't use the repository at all.

**Solution:** Delete the inline SQL from `resource_service.py` and route all persistence through
`ResourcesRepository`. The service becomes responsible only for gathering metrics (CPU, memory,
disk via psutil), formatting them into the domain model, and calling the repository.

**Benefits:**
- **Leverage:** Repository interface stays 2-3 methods. Service stays shallow on top of it.
- **Locality:** SQL structure lives in one place (the repository), not two.
- **Tests:** `ResourcesRepository` already supports `db_provider` injection for in-memory SQLite.
  `resource_service` becomes testable by injecting a fake `ResourcesRepository`.

---

## Candidate 5: Repository singletons prevent test isolation

**Files:** `capsulelab/db/repositories/__init__.py`, all services that import repos

**Problem:** `db/repositories/__init__.py` creates 8 module-level singletons
(`projects = ProjectsRepository()`, `apps = AppsRepository()`, etc.) at import time. Every
service imports these globals directly. Every test must monkeypatch the global to isolate state.
The `db_provider` injection seam on each repository constructor exists but is never exercised —
no factory, no test configuration, no `reset()` method.

This means: tests cannot run against independent in-memory databases per test.
`monkeypatch.setattr` is the *only* isolation strategy, coupling test code to import paths.
A single test that forgets to restore a monkeypatch corrupts state for all subsequent tests.

**Solution:** Replace module-level singletons with a `RepositoryFactory` or a
`register_repositories(provider)` function called once at startup (or per-test). Services accept
repos via constructor injection or a config object. The `__init__.py` re-exports but does not
instantiate.

**Benefits:**
- **Leverage:** One seam (the factory/registration call) replaces 8 separate monkeypatches per
  test.
- **Locality:** Test setup is a one-liner: `repos = RepositoryFactory(in_memory_sqlite)`.
- **Tests:** True parallel test isolation — each test gets a fresh database without
  monkeypatching.

---

## Candidate 6: `projects.py` backend router imports 12 services

**Files:** `backend/api/projects.py` (362 lines, 12 service imports)

**Problem:** A single API router imports 12 of 21 services. Any change to any of those risks
breaking this endpoint. The router handles CRUD, building, starting, stopping, app listings,
build logs, IDE setup, environment, dependencies, resources, compose status, git status, and
secrets — it's a god module routing everything through `project_id`.

**Solution:** Split into domain-aligned sub-routers or route to the existing
`backend/api/` files that already exist for some domains (e.g., `backend/api/resources.py`,
`backend/api/logs.py`).

**Benefits:**
- **Locality:** A change to build behavior touches `ProjectBuildRouter`, not the CRUD handler.
- **Leverage:** Each sub-router imports 2-3 services instead of 12.
- **Tests:** Test each sub-router with focused fakes. No need to stub 12 services to test a
  CRUD endpoint.

---

## Candidate 7: Six persistence patterns with no abstraction

**Files:** SQLite repos, JSON files in `graph_service.py`, `agent_service.py`, `model_service.py`,
`registry_service.py`, YAML in `project_service.py`

**Problem:** Each persistence pattern has its own save/load/error-handling idiom. Adding a new
data type requires choosing from 6 patterns without guidance. Some JSON stores (models, registry
credentials) are simple key-value files; others (graphs) are structured documents with indexing
logic layered on top.

**Solution:** Introduce a thin `DocumentStore` abstraction for the JSON-and-YAML cases
(read/write/delete a document at a path), so each consumer doesn't reimplement
`json.loads`/`except FileNotFoundError`/`json.dumps`. Leave SQLite repos as-is — they already
have a pattern.

**Benefits:**
- **Leverage:** Adding a JSON-backed store is 3 lines instead of a new `_load()`/`_save()` pair.
- **Locality:** Error handling (JSON decode errors, write failures, permissions) is centralized.
