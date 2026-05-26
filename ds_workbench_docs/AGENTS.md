# AGENTS.md
## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
## Project Goal

Build CapsuleLab, a local-first data-science and AI workbench similar in spirit to NVIDIA AI Workbench but with its own product identity, config model, backend, UI language, and agent-native features.

The system should let users create, build, run, understand, polish, and move reproducible data-science projects across machines such as a laptop, gaming PC, DGX Spark, remote server, or cloud GPU.

The core product is not just a notebook launcher. It is a capsule workbench: runtime manager, app launcher, Git/project manager, agent workspace, knowledge graph, and deployment/open-source readiness tool.

This app is for personal, local use. It should not be designed as a hosted SaaS product. It may be published on GitHub as open source, but implementation decisions should assume local installation, local data, local credentials, and single-user control.

## Core Product Idea

A project is a Git-backed capsule with:

- a containerized runtime
- a project configuration file
- app launchers
- dataset/model mounts
- environment variables
- local and remote execution support
- run history and reproducibility checks
- agent and knowledge-graph context

The same project should run locally or remotely with minimal changes.

Projects should support three profiles:

- `research` for notebooks, experiments, datasets, papers, models, and run reports.
- `deployable` for APIs, apps, Docker packaging, health checks, tests, logs, and deployment manifests.
- `opensource` for README/license/contributing/docs/examples/package metadata, CI templates, and release readiness.

## Primary User Flow

1. User creates a project from a template.
2. User chooses an environment such as CPU Python, PyTorch CUDA, TensorFlow CUDA, RAPIDS, RAG stack, or custom Dockerfile.
3. Workbench generates config files and a Dockerfile.
4. User builds the runtime.
5. User starts the project.
6. User launches apps such as JupyterLab, VS Code Server, Streamlit, Gradio, MLflow, or TensorBoard.
7. User syncs the project with Git.
8. User can move the same project to a remote machine.

## MVP Scope

Implement these features first:

- `cap init`
- `cap doctor`
- `cap build`
- `cap start`
- `cap stop`
- `cap logs`
- `cap app list`
- `cap app start jupyter`
- `cap app open jupyter`
- `cap app stop jupyter`
- `cap app logs jupyter`

After the CLI runtime is reliable, add:

- FastAPI backend exposing the same operations
- React dashboard listing projects
- Project detail page with Build, Start, Stop, Logs, and Open App buttons

Do not implement Kubernetes in the MVP.

## Recommended Stack

### Frontend

- React
- TypeScript
- Tailwind CSS

### Backend

- FastAPI
- SQLite
- Pydantic
- Docker SDK for Python or subprocess-based Docker wrapper

### CLI

- Python
- Typer
- Rich for terminal output

### Runtime

- Docker first
- Podman later
- Docker Compose for multi-service projects later

### Remote Execution

- SSH first
- Remote Python agent later

## Repository Structure

Recommended initial structure:

```txt
capsulelab/
  AGENTS.md
  README.md
  docs/
    ARCHITECTURE.md
    ROADMAP.md
    PROJECT_SPEC.md
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
  cli/
    main.py
    commands/
      init.py
      build.py
      start.py
      stop.py
      logs.py
      app.py
  frontend/
    src/
      pages/
      components/
      api/
  templates/
    python-basic/
    pytorch-cuda/
    streamlit-dashboard/
    research-rag/
    deployable-fastapi/
    opensource-python-package/
```

## Coding Rules

- Prefer small, focused files.
- Keep the CLI and backend using the same service layer when possible.
- Keep the CLI-first runtime path working before adding UI behavior.
- Do not hardcode project paths.
- All current project behavior should come from `.workbench/project.yaml`; design new schema with a future `capsule.yaml` manifest in mind.
- Always validate YAML config before running containers.
- Do not silently swallow Docker errors.
- Return useful error messages that explain the failed command and likely fix.
- Keep local execution working before adding remote execution.
- Avoid Kubernetes until local Docker and SSH workflows are stable.

## Runtime Rules

The runtime manager must support:

- build image
- start container
- stop container
- stream logs
- exec commands
- detect GPU support
- mount project folder
- mount dataset folders
- expose app ports
- run detached app processes
- stop individual app processes
- track app health and runtime state
- expose app-level logs

## Project Config Rules

Each project should contain:

```txt
.workbench/
  project.yaml
Dockerfile
README.md
notebooks/
src/
data/
models/
```

The config file should define:

- project name
- runtime type
- Dockerfile path
- image name
- GPU setting
- mounts
- environment variables
- apps

## App Launcher Rules

An app is a command inside the running project container.

Example apps:

- JupyterLab
- VS Code Server
- Streamlit
- Gradio
- MLflow
- TensorBoard

Each app should define:

- name
- command
- port
- URL path
- health check, optional

The app config defines desired behavior. Runtime details such as process IDs, current health, last start time, and log locations should live in runtime state, not in `.workbench/project.yaml`.

## Remote Execution Rules

Start with SSH-based remote execution.

The remote machine should:

- have Docker installed
- have the project folder cloned or synced
- run the same CLI commands remotely

Do not require a remote agent in the MVP.

## Important Non-Goals for MVP

Do not build these first:

- Kubernetes cluster manager
- multi-user permissions
- cloud billing system
- full dataset versioning
- model registry
- custom package manager
- hosted SaaS backend
- complex secrets manager
- large template catalog
- remote runtime agent
- production deployment infrastructure
- account system

## Product Concerns

- Avoid becoming a broad platform before the local Docker runner is dependable.
- Do not treat the product as a notebook launcher; the durable value is portable project runtime management.
- Keep templates few and reliable at first.
- Add reproducibility checks early through `cap doctor`.
- Make app lifecycle management explicit: start, health, logs, stop, and failure detection.

## Definition of Done for MVP

The MVP is complete when a user can:

```bash
cap init demo --template pytorch-cuda
cd demo
cap doctor
cap build
cap start
cap app start jupyter
cap app open jupyter
cap app logs jupyter
cap app stop jupyter
cap logs
cap stop
```

After this works reliably from the CLI, the same operations should become visible from the FastAPI backend and React UI.
