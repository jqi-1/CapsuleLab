# Roadmap

## Phase 1: CLI-Only Local Runner

Goal: prove the core runtime model.

Implement:

- `wb init`
- `wb doctor`
- `wb build`
- `wb start`
- `wb stop`
- `wb logs`

Acceptance test:

```bash
wb init demo --template pytorch-cuda
cd demo
wb doctor
wb build
wb start
wb logs
wb stop
```

Output should be clear and useful.

`wb doctor` should perform the earliest reproducibility and readiness checks:

- missing Dockerfile
- missing `.workbench/project.yaml`
- invalid project config
- Docker unavailable
- GPU requested but unavailable
- missing README
- obvious port conflicts

## Phase 2: App Launcher

Goal: launch useful tools inside the running project container.

Implement:

- `wb app list`
- `wb app start jupyter`
- `wb app open jupyter`
- `wb app stop jupyter`
- `wb app logs jupyter`
- `wb app start vscode`
- `wb app start streamlit`
- app health checking
- app process state tracking
- port conflict detection

Acceptance test:

```bash
wb app start jupyter
wb app open jupyter
wb app logs jupyter
wb app stop jupyter
```

The browser should open JupyterLab.

Concern to resolve in this phase: launching an app with `docker exec -d` is not enough. The workbench should be able to answer whether the app is running, where logs are stored, how to stop only that app, and what happened if the app exits.

## Phase 3: Project Templates

Goal: make new projects useful immediately.

Initial templates:

- `python-basic`
- `pytorch-cuda`
- `streamlit-dashboard`

Later templates:

- `tensorflow-cuda`
- `rag-stack`
- `computer-vision`
- `llm-inference`

Each template should include:

- Dockerfile
- `.workbench/project.yaml`
- README
- starter notebook or app
- requirements file

Concern: each template becomes a maintenance commitment. Prefer a small number of reliable templates over a large catalog of stale ones.

## Phase 4: FastAPI Backend

Goal: expose the CLI functionality to a UI.

Implement:

```txt
GET  /projects
POST /projects
GET  /projects/{id}
POST /projects/{id}/build
POST /projects/{id}/start
POST /projects/{id}/stop
GET  /projects/{id}/logs
GET  /projects/{id}/apps
POST /projects/{id}/apps/{app}/start
POST /projects/{id}/apps/{app}/stop
GET  /projects/{id}/apps/{app}/logs
```

The backend should call the same service layer used by the CLI.

## Phase 5: React UI

Goal: make the product usable without the terminal.

Pages:

- Dashboard
- Projects
- Project detail
- Create project
- App launcher
- Logs viewer
- Settings

Project detail should show:

- build status
- running/stopped status
- Git branch
- container name
- exposed apps
- GPU availability
- recent logs

## Phase 6: Remote SSH Execution

Goal: run the same project on another machine.

Implement:

- `wb locations add`
- `wb locations list`
- `wb start --location dgx-spark`
- `wb logs --location dgx-spark`
- remote Docker check
- remote GPU check

Start with SSH commands. Do not build a remote agent yet.

## Phase 7: Docker Compose Support

Goal: support multi-service data and AI apps.

Use cases:

- RAG stack with Qdrant
- MLflow plus Postgres
- FastAPI model server plus frontend
- app plus database

Implement:

- detect `docker-compose.yaml`
- `wb compose up`
- `wb compose down`
- service logs
- service health display

## Phase 8: Dataset and Cache Manager

Goal: reduce repeated setup for datasets and model downloads.

Implement:

- dataset mounts
- model mounts
- Hugging Face cache mount
- PyTorch cache mount
- dataset registry in project config

Example:

```yaml
caches:
  huggingface:
    source: ~/.cache/huggingface
    target: /root/.cache/huggingface
```

## Phase 9: Reproducibility Checks

Goal: expand `wb doctor` from basic readiness checks into deeper reproducibility guidance.

Warn about:

- no Dockerfile
- no lockfile
- unpinned packages
- missing README
- missing project config
- uncommitted Git changes
- undefined dataset paths
- invalid app ports

These checks should start simple in Phase 1 and become more sophisticated here. They should remain warnings unless the issue prevents execution.

## Phase 10: Remote Agent

Goal: improve remote execution beyond raw SSH commands.

The agent can provide:

- stable logs streaming
- better process tracking
- remote app health checks
- remote file sync
- authentication
- machine metrics
- GPU metrics

Do this only after SSH mode works well.
