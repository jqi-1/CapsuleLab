# CapsuleLab

**Local-first containerized project runtime manager for reproducible AI and data-science work.**

Make your development environment portable across machines — laptop, gaming PC, DGX Spark, remote server, or cloud GPU — with one CLI command.

```bash
cap init my-project --template pytorch-cuda
cd my-project
cap doctor       # check everything is ready
cap build        # build the container image
cap start        # launch the runtime
cap app start jupyter
cap app open jupyter
```

## Why CapsuleLab

Every data-science project has a setup ritual: Python version, CUDA toolkit, pip packages, dataset paths, environment variables, Jupyter config, port mappings. CapsuleLab encodes that ritual into a **capsule** — a Git-backed project folder with a `capsule.yaml` manifest, a Dockerfile, and a few conventions — so it works the same way on any machine.

Designed for the workflow:

```
Project → Environment → Build → Run → Apps → Logs → Git → Remote Machine
```

## Features

- **Project profiles** — `research`, `deployable`, and `opensource` modes tune templates, validation, and dashboard emphasis without splitting the product
- **Containerized runtime** — Docker (single-container or Compose) with automatic GPU detection, volume mounts, and port mapping
- **App launchers** — Start/stop/open/log JupyterLab, VS Code Server, Streamlit, Gradio, TensorBoard, or any process inside the runtime container
- **SSH remote execution** — Deploy and run projects on remote machines via SSH with rsync sync; no remote agent required for basic use
- **Lightweight remote agent** — Optional `capsulelab_agent.py` for structured remote Docker management
- **Reproducibility checks** — `cap doctor` validates Docker, GPU, Git, secrets, datasets, caches, and project config before you build
- **Experiment runs** — Lightweight run tracking with artifacts and notes
- **Knowledge graph** — Index project code, notebooks, and papers for agent-assisted understanding
- **Build assistant** — Analyze failed builds and propose fixes
- **Three control surfaces** — `cap` CLI (primary), FastAPI backend, React/Vite dashboard

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (with `nvidia-container-toolkit` for GPU support)
- Node.js 18+ (for the frontend)

### Install

```bash
pip install -e .
```

### Create and run a project

```bash
cap init my-project --template pytorch-cuda
cd my-project
cap doctor
cap build
cap start
cap app start jupyter
cap app open jupyter
```

### Start the API server

```bash
uvicorn backend.main:app --reload
```

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `cap init` | Create a new project from a template |
| `cap doctor` | Check project readiness (Docker, GPU, config, secrets) |
| `cap build` | Build the container image |
| `cap start` | Start the project container |
| `cap stop` | Stop the project container |
| `cap logs` | Stream project logs |
| `cap shell` | Open a shell inside the container |
| `cap exec` | Run a command inside the container |
| `cap app` | Manage apps (start/stop/open/logs/list) |
| `cap compose` | Manage Docker Compose stacks |
| `cap location` | Manage remote SSH locations |
| `cap sync` | Sync project to a remote location |
| `cap template` | List and inspect templates |
| `cap project` | Register, list, and inspect projects |
| `cap secrets` | Manage project secrets |
| `cap runs` | Track experiment runs |
| `cap images` | Check and catalog Docker images |
| `cap resources` | View system resource usage |
| `cap data` | Manage dataset mounts |
| `cap ide` | Attach IDE (Cursor, VS Code, Windsurf) |
| `cap package` | Export/import portable capsule snapshots |
| `cap graph` | Index and query the project knowledge graph |
| `cap registry` | Manage image registry settings |
| `cap metadata` | View project metadata |
| `cap settings` | Configure CapsuleLab settings |
| `cap profile` | Manage project profiles |

## Project Structure

```
my-project/
  .workbench/
    project.yaml       # project config (desired state)
  capsule.yaml         # target public manifest
  Dockerfile
  docker-compose.yml   # optional multi-service config
  notebooks/
  src/
  data/
  models/
  README.md
```

## Templates

| Template | GPU | Profile | Use case |
|----------|-----|---------|----------|
| `python-basic` | No | research | Minimal Python + JupyterLab |
| `pytorch-cuda` | Yes | research | PyTorch + CUDA + Jupyter + Streamlit |
| `streamlit-dashboard` | No | research | Streamlit dashboard app |
| `research-rag` | No | research | RAG stack with notebooks |
| `deployable-fastapi` | No | deployable | FastAPI model API with checks |
| `opensource-python-package` | No | opensource | PyPI-ready Python package |

## Architecture

Three control surfaces share one service layer:

```
cap CLI          FastAPI /api          React/Vite UI
     \               |               /
      \              |              /
       └──── Service Layer ────────┘
                |        |
      Project Runtime   SQLite State
       (Docker/SSH)     (~/.capsulelab/capsulelab.db)
```

- **CLI** — primary builder and debugging surface (Typer + Rich)
- **Backend** — FastAPI with SQLite for observed/host-specific state
- **Frontend** — React + TypeScript + Tailwind CSS + Vite
- **Service layer** — 28 modules covering Docker, SSH, Git, GPU, apps, Compose, secrets, runs, images, templates, profiles, knowledge graph, and more

## Project Profiles

Profiles tune defaults without forking the product:

- **research** — notebooks, experiments, datasets, model comparison, run reports, knowledge graph
- **deployable** — APIs, health checks, tests, env validation, secrets scan, deployment manifests
- **opensource** — README/license/CONTRIBUTING checks, docs preview, examples, CI templates

## Testing

```bash
pytest                          # all tests
pytest -m pure_config           # tests requiring no Docker/SSH
pytest -m docker                # tests requiring Docker daemon
pytest -m ssh                   # tests requiring SSH host
```

## Motivation

CapsuleLab is inspired by the category NVIDIA AI Workbench defined, but built as a distinct product: different config schema, visual language, template model, and agent-native features. It is designed for **local-first, portable reproducibility** — the same capsule runs on your laptop, a DGX Spark, a gaming PC, or a cloud GPU server with minimal changes.

## License

MIT
