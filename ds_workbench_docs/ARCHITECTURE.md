# Architecture

## Purpose

CapsuleLab is a local-first control plane for reproducible, containerized AI and data-science projects. It should make a project portable across machines while keeping code, data paths, credentials, Docker access, and runtime state under the user's control.

The core product object is a capsule: a portable package containing code, environment, launchable apps, data and model mounts, secret references, run history, agent context, project metadata, and project knowledge.

The architecture is intentionally smaller than NVIDIA AI Workbench, but it follows several proven ideas from that product category:

- versioned project configuration
- local and remote locations
- reproducible containers
- managed web applications
- Git-aware project workflows
- IDE and agent work inside a project boundary
- project knowledge graphs and agent-readable context
- orchestrator-style visibility across builds, runs, apps, logs, Git, resources, and locations
- multi-container support for real AI systems
- clear separation between portable project intent and host-specific state

## Current System Shape

```txt
┌────────────────────────────────────────────────────────────┐
│                    Control Surfaces                        │
│                                                            │
│   cap CLI          FastAPI /api          React/Vite UI      │
└──────────────┬───────────────┬─────────────────────────────┘
               │               │
               └───────┬───────┘
                       v
┌────────────────────────────────────────────────────────────┐
│                    Service Layer                           │
│                                                            │
│ project   docker   app       compose   ssh      template   │
│ git       image    resource  secrets   runs     data       │
│ agent     graph    profile   package   deploy              │
└──────────────┬─────────────────────────────────────────────┘
               │
               v
┌────────────────────────────────────────────────────────────┐
│                 State And Configuration                    │
│                                                            │
│ .workbench/project.yaml     ~/.capsulelab/capsulelab.db     │
│ capsule.yaml target          local observed/private state   │
└──────────────┬─────────────────────────────────────────────┘
               │
               v
┌────────────────────────────────────────────────────────────┐
│                  Execution Adapters                        │
│                                                            │
│ local Docker       SSH + Docker       Docker Compose        │
│ GPU checks         rsync sync         logs/status/ports     │
└──────────────┬─────────────────────────────────────────────┘
               │
               v
┌────────────────────────────────────────────────────────────┐
│                    Project Runtime                         │
│                                                            │
│ a single project container or compose stack around a repo   │
└────────────────────────────────────────────────────────────┘
```

The CLI and API should be thin wrappers over services. The UI should consume API facts, not infer Docker, Git, SSH, Compose, or app state in the browser.

## Next Architecture Stages

The next stages should deepen the current architecture rather than widen it too quickly. Each stage should leave the CLI, API, and UI using the same service-layer facts.

### Stage 1: Runtime Parity And Project Doctor

Status: Done

Goal: make the existing local workbench trustworthy.

Build:

- shared error types for expected Docker, config, GPU, port, app, Git, secret, dataset, and stale-state failures
- one canonical project status shape used by CLI, API, and UI
- project-level doctor reports that combine environment, manifest, Dockerfile, image, apps, Git, secrets, datasets, caches, package files, and build metadata
- app lifecycle cleanup when containers restart or app processes disappear
- smoke-test boundaries for pure config checks, Docker checks, SSH checks, and Compose checks

Architecture impact:

- Add a small shared error model under `backend/models` or `backend/services` before expanding route behavior.
- Keep `doctor_service.py` as the aggregator rather than spreading readiness checks across route handlers and UI components.
- Treat project status as a service-owned DTO; the frontend renders it without reconstructing runtime state.

### Stage 2: Profiles, Templates, And Manifest Evolution

Status: In progress

Goal: introduce `research`, `deployable`, and `opensource` profiles as defaults and checks, not separate runtimes.

Build:

- `mode` and `presets` in the current `.workbench/project.yaml`
- profile-aware template metadata in `templates/manifest.json`
- profile-specific doctor checks and UI dashboard hints
- first maintained profile templates: `research-rag`, `deployable-fastapi`, and `opensource-python-package`
- a documented migration path from `.workbench/project.yaml` toward top-level `capsule.yaml`

Architecture impact:

- Add `profile_service.py` only when more than one command or route needs profile decisions.
- Keep profile behavior declarative: profiles choose defaults, checks, and dashboard emphasis; they should not fork project loading, runtime startup, or app lifecycle logic.
- Do not rename the current manifest path until the code can read both old and new paths and write one canonical format.

### Stage 3: Managed Apps, URLs, And Remote Locations

Status: In progress

Goal: make local and SSH projects feel consistent when launching web apps, process apps, and Compose apps.

Build:

- stronger app state based on PID, port, healthcheck, log path, recent exit state, and owning container
- stable local URL formation, with an optional reverse proxy after direct URLs are reliable
- remote location status that reports SSH, Docker, GPU, disk, project root, and tunnel assumptions
- per-location path mapping for datasets, caches, and secrets
- Compose service status folded into the same project status vocabulary as single-container projects

Architecture impact:

- Keep `app_service.py` responsible for app state, not the UI.
- Keep `ssh_service.py` as a transport adapter until raw SSH behavior is exhausted.
- Introduce a proxy service only after direct local and SSH URL rules are documented and tested.
- Avoid a remote daemon until the SSH model has clear performance or lifecycle problems that cannot be solved cleanly.

### Stage 4: Knowledge Graph And Agent Workspace

Status: In progress

Goal: make projects understandable to agents and users without letting agents escape the capsule boundary.

Build:

- local project graph index for code, notebooks, papers, configs, docs, runs, apps, templates, and manifest data
- generated project summaries for setup, architecture, app usage, data/model mounts, recent runs, and known readiness issues
- reviewed agent actions for build fixes, README/docs updates, benchmark interpretation, and experiment reports
- local storage policy for graph indexes and agent scratch state

Architecture impact:

- Add `graph_service.py` as a local index manager; it should read project files and local state but not become a second source of truth.
- Add `agent_service.py` as an orchestration boundary for prompts, allowed files, reviewed edits, and action history.
- Store graph indexes and agent scratch data outside the project unless the user explicitly exports generated artifacts.

### Stage 5: Packaging, Deployment Readiness, And Open-Source Release

Status: In progress

Goal: help users turn a capsule into a deployable or public artifact while preserving local-first control.

Build:

- deployable profile checks for health endpoints, env validation, secrets scan, tests, logs, Dockerfile quality, dependency scan, and deployment manifest
- open-source profile checks for README, license, contributing guide, examples, docs, package metadata, GitHub templates, CI, changelog, and release checklist
- package/export flow that can produce a shareable capsule snapshot without local secrets or machine-specific paths
- registry and publish helpers only after local packaging rules are reliable

Architecture impact:

- Add package/deploy services only around concrete workflows; avoid a generic plugin system until there are repeated extension points.
- Treat deployment manifests and release docs as generated project artifacts that require user review before writing.
- Keep hosted accounts, billing, multi-user permissions, and Kubernetes outside the architecture until the local packaging story is solid.

## Desired State: Project Manifest

The project config is the portable contract that belongs in the project repository. The current implementation uses `.workbench/project.yaml`; the target public manifest name is `capsule.yaml`.

Current model:

- project name and description
- project profile: `research`, `deployable`, or `opensource`
- runtime type, Dockerfile, image, and GPU request
- mounts
- cache mounts
- datasets
- required secret references
- environment variables
- launchable apps with commands, ports, URL paths, health checks, and kind
- optional agent and knowledge-graph settings

The config should describe what should exist, not what happened last time. It must not store PIDs, container IDs, app health, log offsets, local secret values, remote sync timestamps, or last start times.

Future config pressure should be handled conservatively. Add fields only when at least one real template or workflow needs them.

## Project Profiles

Profiles tune the product around three common jobs:

- `research`: notebook-first experiments, papers, datasets, models, run comparison, reports, and knowledge graphs.
- `deployable`: API/service/app packaging, Docker checks, health checks, secrets scans, tests, logs, and deployment manifests.
- `opensource`: public project polish, README/license/contributing/docs/examples/package metadata, GitHub automation, and release checklists.

Profiles should influence template selection, validation, dashboard layout, recommended apps, and generated docs. They should reuse the same manifest, service layer, runtime model, and local database.

## Local State: SQLite

SQLite stores CapsuleLab-owned state that is either observed, private, or host-specific.

Current location:

```txt
~/.capsulelab/capsulelab.db
```

State categories:

- registered projects and paths
- app runtime state
- build metadata
- SSH locations
- local secret values or secret presence metadata
- lightweight experiment runs
- local settings-style facts

Runtime state may be stale. Before reporting something as live, services should re-check Docker, SSH, Compose, or the filesystem.

## Control Surfaces

### CLI

`cap` is the primary builder and debugging surface. It may print human-friendly tables, open browsers, prompt for secrets, and expose power-user commands.

Current command groups:

- `cap init`
- `cap doctor`
- `cap build`
- `cap start`
- `cap stop`
- `cap logs`
- `cap app ...`
- `cap location ...`
- `cap compose ...`
- `cap sync ...`
- `cap template ...`
- `cap project ...`
- `cap secrets ...`
- `cap runs ...`
- `cap resources ...`
- `cap images ...`
- `cap data ...`

CLI commands should delegate business rules to `backend/services`. If a command needs logic the API or UI will also need, put it in a service first.

### FastAPI Backend

The backend is the local control API. It initializes SQLite on startup and exposes project/runtime operations under `/api`.

Current route areas:

```txt
GET  /api/health
GET  /api/doctor

GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/build
POST /api/projects/{project_id}/start
POST /api/projects/{project_id}/stop
GET  /api/projects/{project_id}/status
GET  /api/projects/{project_id}/logs

GET  /api/projects/{project_id}/apps
POST /api/projects/{project_id}/apps/{app_id}/start
POST /api/projects/{project_id}/apps/{app_id}/stop
GET  /api/projects/{project_id}/apps/{app_id}/status
GET  /api/projects/{project_id}/apps/{app_id}/logs

GET  /api/projects/{project_id}/compose/status
POST /api/projects/{project_id}/compose/up
POST /api/projects/{project_id}/compose/down
GET  /api/projects/{project_id}/compose/logs

GET  /api/projects/{project_id}/git/status
GET  /api/projects/{project_id}/secrets
GET  /api/projects/{project_id}/runs
POST /api/projects/{project_id}/runs
POST /api/projects/{project_id}/runs/{run_id}/finish
GET  /api/projects/{project_id}/resources
GET  /api/projects/{project_id}/images/check
GET  /api/projects/{project_id}/images/catalog

GET  /api/locations
GET  /api/locations/{name}/status
```

API handlers should validate request shape, load local state, call services, and translate known failures into useful HTTP errors.

### Frontend

The React/Vite frontend is a local operator console.

Current capabilities:

- list registered projects
- create projects from templates
- inspect project config and runtime status
- build, start, and stop project containers
- view logs
- start, stop, open, and inspect apps
- show readiness, Docker/GPU, Git, resources, secrets, and build metadata
- show Compose status and actions
- show locations and location status

The UI must not construct Docker commands or assume runtime state independently. It should present API status and actions clearly.

## Service Modules

Current modules:

```txt
backend/services/
  app_service.py
  build_assistant_service.py
  compose_service.py
  doctor_service.py
  docker_service.py
  git_service.py
  gpu_service.py
  ide_service.py
  image_service.py
  location_override_service.py
  package_service.py
  project_service.py
  resource_service.py
  run_service.py
  secrets_service.py
  ssh_service.py
  template_service.py
```

Ownership:

- `project_service.py`: project path resolution, config loading, validation, project IDs, container names, template creation.
- `docker_service.py`: Docker availability, build/run/stop/logs/exec/inspect/ps, ports, labels, image inspection, app log conventions.
- `app_service.py`: app start/stop/status/logs inside a running project container.
- `compose_service.py`: Compose file detection, up/down/status/logs.
- `gpu_service.py`: local GPU detection, `nvidia-smi`, Docker GPU runtime checks.
- `ssh_service.py`: SSH command execution, remote Docker/GPU status, remote path conventions, rsync sync.
- `git_service.py`: repository status, branch, remote, dirty file count, Git LFS availability.
- `image_service.py`: BYOC checks and image catalog metadata.
- `resource_service.py`: disk and GPU resource summaries.
- `run_service.py`: lightweight local experiment run registry.
- `secrets_service.py`: project secret storage/presence outside the repo.
- `template_service.py`: template catalog and template checks.
- `location_override_service.py`: per-location path overrides for datasets, caches, and secrets.
- `package_service.py`: capsule export/import for portable project snapshots.
- `build_assistant_service.py`: failed-build log analysis and constrained build-script edit proposals.
- `doctor_service.py`: project-level reproducibility report aggregating environment, config, Docker, GPU, Git, secrets, datasets, caches, and build checks.
- `ide_service.py`: IDE attach helpers for Cursor, VS Code, and Windsurf with project rules generation.
- future `profile_service.py`: profile-specific defaults, validation checks, and dashboard hints.
- future `agent_service.py`: agent workspace setup, prompt/context boundaries, and reviewed agent actions.
- future `graph_service.py`: project knowledge graph indexing, paper/source links, and agent-readable summaries.

The service layer is the product core. Control surfaces should not grow duplicate lifecycle behavior.

## Runtime Model

### Single-Container Runtime

The default runtime is one long-lived Docker container per project. The project is mounted into `/workspace`, app ports are mapped, cache and dataset mounts are attached, optional GPU access is enabled, and the container stays alive while apps run inside it.

Representative shape:

```bash
docker run -d \
  --name cap-my-project \
  --gpus all \
  -v "/path/to/project:/workspace" \
  -w /workspace \
  -p 8888:8888 \
  image-name:dev \
  sleep infinity
```

Apps launch through `docker exec` inside the project container. App definitions live in `.workbench/project.yaml`; app runtime observations live in SQLite.

Hardening direction:

- verify container ownership before stop/remove
- detect stale app state after container restart
- validate ports before launch
- report healthcheck failures clearly
- standardize log paths and app URLs
- support stable app proxying later

### Compose Runtime

Compose is the multi-service adapter for RAG stacks, model servers, MLflow plus databases, app-plus-worker systems, and other projects that should not be forced into one container.

Compose should remain explicit. The architecture must distinguish:

- the project container, when present
- the Compose stack
- service health
- service logs
- ports and app URLs
- shared networks and volumes

Before adding more Compose UI, define a stable status shape that can survive different Compose file layouts.

### SSH Runtime

SSH locations are the first remote adapter. CapsuleLab currently uses SSH command execution and rsync rather than installing a remote CapsuleLab service.

SSH mode should own:

- reachability
- remote Docker availability
- remote GPU availability
- project root and remote project path
- remote sync
- remote start/stop/logs
- remote app URL formation

This is intentionally less abstract than NVIDIA AI Workbench's remote service/proxy tunnel model. Do not add a remote agent until SSH behavior is stable and the missing parity is well understood.

## Data, Secrets, And Host-Specific Values

CapsuleLab should keep portable project intent separate from local reality.

Versioned in the project:

- required secret names
- dataset logical names and target paths
- cache mount intent
- app commands and ports
- selected project profile and safe preset flags
- agent/knowledge graph intent that is safe to share
- environment variable names only when safe

Local or per-location:

- secret values
- host dataset paths
- cache source paths
- remote project roots
- SSH keys and usernames
- machine capability facts
- local graph indexes and agent scratch state, unless explicitly exported

This boundary is essential for Git workflows and safe sharing.

## Git And Project Lifecycle

AI Workbench treats a project as a managed Git repository with visible code and environment changes. CapsuleLab already reports Git status but still needs full lifecycle workflows:

- import an existing path
- clone a repo and scaffold missing config
- repair project inventory
- detect publish readiness
- show dirty files before build/run
- avoid writing secrets or local-only paths into Git-tracked files

Git should be treated as a first-class reproducibility signal, not a decorative status line.

## NVIDIA AI Workbench Gap Map

The current repo covers the beginning of these areas:

- project config and reproducible containers
- local CLI/API/UI surfaces
- apps inside containers
- Docker Compose
- SSH locations
- Git/resource/secrets/run metadata
- data/cache declarations
- templates

Missing or partial compared with NVIDIA AI Workbench:

- feature parity between desktop UI and CLI
- remote location service tunnels and proxy tunnels
- secure shared URLs for running web apps
- first-class clone/import/publish Git workflows
- IDE attach helpers for VS Code, Cursor, and Windsurf
- explicit coding-agent workspace workflow
- project knowledge graph and agent-readable project memory
- profile-specific dashboards and checks for research, deployable, and open-source projects
- build assistant or structured build failure diagnosis
- automatic management of system dependencies such as drivers/container toolkit
- richer environment editing that writes config back safely
- NGC, GitHub/GitLab, Brev, Endpoints, and registry integrations
- robust custom base image workflow
- project deep links
- settings for proxy, certificates, runtime choices, and app components

CapsuleLab should close the gaps that strengthen local-first reproducibility and defer hosted/cloud-heavy features until the local and SSH story is solid.

## Architecture Rules

- Put shared behavior in services before exposing it in CLI, API, or UI.
- Keep the project manifest as desired state and SQLite as observed/private/local state.
- Treat `.workbench/project.yaml` as the current manifest path and `capsule.yaml` as the target public contract.
- Re-check live runtime facts before reporting them.
- Prefer clear failure messages over clever recovery.
- Do not store secret values in project files.
- Do not let remote execution imply a remote agent unless one exists.
- Keep templates small, maintained, and smoke-testable.
- Add schema only when a real workflow needs it.
- Treat Git state, package files, datasets, caches, secrets, and build metadata as reproducibility inputs.
