# Project Spec

## Capsule Contract

A CapsuleLab project is a portable capsule: source code, runtime environment, launchable apps, data/model mounts, secret references, runs, agents, and project knowledge stored around one Git-backed project folder.

The current implementation stores desired state in `.workbench/project.yaml`. The long-term public config should converge on `capsule.yaml` once the migration path is explicit. Until then, docs should name both carefully:

- `.workbench/project.yaml`: current source of truth used by the codebase.
- `capsule.yaml`: target top-level capsule manifest and schema direction.

## Standard Project Layout

Each CapsuleLab project should look like this:

```txt
my-project/
  .workbench/
    project.yaml
    runtime.yaml
    apps.yaml
    secrets.example.yaml
  Dockerfile
  docker-compose.yaml
  notebooks/
  src/
  data/
  models/
  README.md
```

For the MVP, only this is required:

```txt
my-project/
  .workbench/
    project.yaml
  Dockerfile
  README.md
  notebooks/
  src/
  data/
  models/
```

## Project Profiles

Profiles change defaults, templates, dashboard emphasis, and validation checks. They are not separate products.

### Research

Research projects prioritize exploration, notebooks, experiments, papers, datasets, models, and reproducibility.

Default layout:

```txt
project/
  notebooks/
  src/
  data/
  models/
  experiments/
  papers/
  outputs/
  reports/
  capsule.yaml
```

Recommended defaults:

```yaml
mode: research

presets:
  notebook_first: true
  experiment_tracking: true
  dataset_mounts: true
  model_cache: true
  knowledge_graph: true
  paper_notes: true
  reproducibility_checks: true
```

Expected apps and checks include JupyterLab, TensorBoard, Gradio, Streamlit, MLflow or a lightweight experiment tracker, notebook summaries, dataset notes, model comparisons, run-diff analysis, paper/source graphing, and experiment reports.

### Deployable

Deployable projects prioritize turning local AI/data-science work into a service, app, or containerized package that can run in production-like environments.

Default layout:

```txt
project/
  app/
  src/
  tests/
  configs/
  docker/
  scripts/
  data/
  models/
  docs/
  capsule.yaml
  Dockerfile
  docker-compose.yml
```

Recommended defaults:

```yaml
mode: deployable

presets:
  api_server: true
  dockerfile_required: true
  health_checks: true
  env_validation: true
  tests_required: true
  secrets_scan: true
  deployment_manifest: true
  logging_dashboard: true
```

Expected apps and checks include FastAPI, Gradio, Streamlit, Docker runtime, API tester, health dashboard, runtime/build logs, port management, GPU compatibility, dependency and secret scans, test coverage, and deployment readiness.

### Open Source

Open-source projects prioritize public sharing, contributor experience, reusable examples, package metadata, and release readiness.

Default layout:

```txt
project/
  src/
  tests/
  docs/
  examples/
  scripts/
  assets/
  .github/
  capsule.yaml
  README.md
  LICENSE
  CONTRIBUTING.md
  CHANGELOG.md
```

Recommended defaults:

```yaml
mode: opensource

presets:
  readme_required: true
  license_required: true
  contributing_required: true
  tests_required: true
  examples_required: true
  github_actions: true
  docs_preview: true
  package_metadata_check: true
```

Expected apps and checks include README preview, docs preview, test runner, linter, package checker, Git dashboard, license selector, GitHub templates, example validation, changelog assistance, and agent-generated project explanations.

## Main Config File

Path:

```txt
.workbench/project.yaml
```

Keep the MVP config in one file. Split files such as `runtime.yaml` or `apps.yaml` should wait until the single-file config becomes painful in real projects.

Example:

```yaml
name: image-classifier
description: PyTorch image classification experiment

runtime:
  type: docker
  dockerfile: Dockerfile
  image: image-classifier:dev
  gpu: true

mounts:
  - source: .
    target: /workspace
  - source: ./data
    target: /workspace/data
  - source: ./models
    target: /workspace/models

environment:
  PYTHONPATH: /workspace/src
  WANDB_MODE: offline

apps:
  - name: JupyterLab
    id: jupyter
    command: jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
    port: 8888
    url_path: /

  - name: VS Code
    id: vscode
    command: code-server --bind-addr 0.0.0.0:8080 /workspace
    port: 8080
    url_path: /

  - name: Streamlit
    id: streamlit
    command: streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    port: 8501
    url_path: /
```

## Config Schema

### Top-Level Fields

| Field | Required | Description |
|---|---:|---|
| `name` | yes | Project name |
| `description` | no | Human-readable project description |
| `mode` | no | Project profile: `research`, `deployable`, or `opensource` |
| `presets` | no | Profile-specific booleans that enable default checks, apps, and dashboard affordances |
| `runtime` | yes | Runtime definition |
| `mounts` | no | Host-to-container mounts |
| `environment` | no | Environment variables |
| `apps` | no | Launchable apps |

### Runtime Fields

| Field | Required | Description |
|---|---:|---|
| `type` | yes | `docker`, `podman`, or `compose` |
| `dockerfile` | yes for Docker | Path to Dockerfile |
| `image` | yes | Image name and tag |
| `gpu` | no | Whether to request GPU support |

### Mount Fields

| Field | Required | Description |
|---|---:|---|
| `source` | yes | Host path |
| `target` | yes | Container path |
| `read_only` | no | Whether mount is read-only |

### App Fields

| Field | Required | Description |
|---|---:|---|
| `name` | yes | Display name |
| `id` | yes | Stable app identifier |
| `command` | yes | Command to run inside container |
| `port` | yes | Container port |
| `url_path` | no | URL path, default `/` |
| `healthcheck` | no | Optional health check path |

The app config describes desired launch behavior. It should not store transient runtime state such as process IDs, health status, last start time, or log offsets. Runtime state belongs in the workbench database or a host-side state file.

## Example Dockerfile

```dockerfile
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    jupyterlab \
    streamlit \
    gradio \
    pandas \
    numpy \
    scikit-learn \
    matplotlib \
    mlflow

COPY . /workspace

CMD ["bash"]
```

## Example Docker Compose File

Use this later, not necessarily in the MVP.

```yaml
services:
  workbench:
    build: .
    ports:
      - "8888:8888"
      - "8080:8080"
    volumes:
      - .:/workspace
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  mlflow:
    image: ghcr.io/mlflow/mlflow
    ports:
      - "5000:5000"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: example

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
```

## Template Types

Recommended MVP templates:

```txt
python-basic
pytorch-cuda
streamlit-dashboard
```

Later templates:

```txt
research-rag
research-pytorch
research-model-eval
research-fine-tuning
deployable-fastapi
deployable-gradio
deployable-rag-api
deployable-batch-inference
opensource-python-package
opensource-typescript-package
opensource-ai-demo
opensource-research-release
```

Concern: templates should be treated as maintained products. A small set of reliable templates is more valuable than a large list that drifts out of date.

## Reproducibility Warnings

The workbench should warn when a project has:

- no Dockerfile
- no README
- no lockfile
- unpinned packages
- undefined dataset mount
- broken app command
- port conflict
- uncommitted Git changes
- missing `.workbench/project.yaml`
- profile mismatch, such as deployable mode without tests or open-source mode without a license
