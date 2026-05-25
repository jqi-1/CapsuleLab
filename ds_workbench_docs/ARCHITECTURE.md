# Architecture

## Overview

The data-science workbench should use a control-plane and runtime-agent architecture.

The product should stay local-first and CLI-first until the runtime behavior is stable. The UI and API should wrap the same service layer as the CLI rather than becoming a separate product path.

The system has four major parts:

1. Frontend UI
2. Backend API
3. Local or remote execution layer
4. Containerized project runtime

```txt
┌────────────────────────────┐
│        Workbench UI         │
│ React / TypeScript          │
└─────────────┬──────────────┘
              │
              v
┌────────────────────────────┐
│      Control API            │
│ FastAPI                     │
│ - projects                  │
│ - environments              │
│ - locations                 │
│ - apps                      │
│ - logs                      │
└─────────────┬──────────────┘
              │
              v
┌────────────────────────────┐
│      Execution Layer        │
│ Local service or SSH runner │
│ - Docker commands           │
│ - Git commands              │
│ - GPU detection             │
│ - app health checks         │
└─────────────┬──────────────┘
              │
              v
┌────────────────────────────┐
│      Project Runtime        │
│ Container / Compose stack   │
│ - JupyterLab                │
│ - VS Code Server            │
│ - MLflow                    │
│ - Streamlit                 │
│ - Gradio                    │
└────────────────────────────┘
```

## Frontend

The frontend should provide:

- dashboard
- project list
- project detail page
- environment editor
- app launcher
- logs viewer
- locations page
- settings page

Recommended stack:

- React
- TypeScript
- Tailwind CSS
- TanStack Query for API state
- Monaco Editor later for config editing

## Backend

The backend should be a FastAPI service.

Main API areas:

```txt
GET  /projects
POST /projects
GET  /projects/{id}
POST /projects/{id}/build
POST /projects/{id}/start
POST /projects/{id}/stop
GET  /projects/{id}/logs
GET  /projects/{id}/apps
POST /projects/{id}/apps/{app_name}/start
POST /projects/{id}/apps/{app_name}/stop
GET  /locations
POST /locations
```

## Backend Modules

Recommended backend structure:

```txt
backend/
  main.py
  api/
    projects.py
    environments.py
    locations.py
    apps.py
    logs.py
    git.py
  services/
    docker_service.py
    git_service.py
    project_service.py
    ssh_service.py
    gpu_service.py
    app_service.py
  models/
    project.py
    location.py
    app.py
  db/
    sqlite.py
```

## Service Responsibilities

### Project Service

Responsible for:

- creating projects
- loading project configs
- validating project configs
- listing projects
- deleting projects
- exporting projects
- locating project directories

### Docker Service

Responsible for:

- `docker build`
- `docker run`
- `docker stop`
- `docker logs`
- `docker ps`
- `docker exec`
- `docker compose up`
- `docker compose down`

### Git Service

Responsible for:

- clone
- status
- commit
- pull
- push
- branch detection
- remote URL detection

### GPU Service

Responsible for:

- detecting `nvidia-smi`
- checking GPU name
- checking VRAM
- checking CUDA driver version
- checking Docker GPU runtime support
- deciding whether to pass `--gpus all`

### App Service

Responsible for:

- starting JupyterLab
- starting VS Code Server
- starting Streamlit
- starting Gradio
- starting MLflow
- checking app ports
- returning browser URLs
- tracking app process state
- stopping individual app processes
- collecting app-level logs

### SSH Service

Responsible for:

- storing remote location configs
- running commands through SSH
- checking remote Docker availability
- starting projects on remote hosts
- streaming remote logs

## Runtime Model

The local runtime should use Docker first.

A basic start command should behave like:

```bash
docker run -d \
  --name wb-my-project \
  --gpus all \
  -v "$PWD:/workspace" \
  -w /workspace \
  -p 8888:8888 \
  -p 8080:8080 \
  image-name:dev \
  sleep infinity
```

The project container should stay alive while app commands are launched inside it through `docker exec`.

## App Launch Model

An app is a command launched inside the running container.

Example:

```bash
docker exec -d wb-my-project \
  jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

The workbench should then return:

```txt
http://localhost:8888
```

Launching an app is not enough. The workbench also needs an app lifecycle model:

- know whether the app is starting, healthy, stopped, or failed
- keep enough process metadata to stop the app without stopping the whole project container
- store or stream app-specific logs
- detect when an app exits unexpectedly
- handle port conflicts before launching

For the MVP, this can be lightweight state in SQLite or a host-side runtime state file. The project config should describe desired apps; runtime state should describe what is currently running.

## Database

Start with SQLite.

Store:

- known projects
- project paths
- recent projects
- locations
- app runtime state
- user settings

Do not duplicate all project config in the database. The source of truth should remain the project files.

The database may cache runtime observations, but it should not become the canonical definition of a project. Project portability depends on the Git-backed project folder remaining sufficient to rebuild and run the project elsewhere.

## Remote Locations

A location is a machine where a project can run.

Example:

```yaml
name: dgx-spark
type: ssh
host: 192.168.1.50
user: jeremy
project_root: /home/jeremy/workbench-projects
runtime: docker
gpu: true
```

## Local-First Principle

The workbench should work fully offline for local projects.

Cloud, sync, and account features should not be required for the core workflow.

## Deployment Assumption

The workbench is not intended to be deployed as a hosted production service. It should run on a user's own machine and optionally control other machines through local configuration, SSH, and Git.

If the project is open-sourced, distribution should still favor local installation and self-contained setup. Avoid architecture that depends on central accounts, hosted control planes, production observability stacks, multi-tenant permissions, or cloud billing.

## Architecture Concerns

- Avoid building a broad platform before the local Docker runner is reliable.
- Keep the CLI, API, and UI on one shared service layer.
- Treat remote SSH execution as a transport for the same project operations, not a second runtime model.
- Delay a remote agent until raw SSH exposes clear pain that an agent would solve.
- Keep Kubernetes, multi-user permissions, hosted SaaS features, and cloud billing out of the early architecture.
- Prefer local files, local SQLite, and local configuration over hosted infrastructure.
