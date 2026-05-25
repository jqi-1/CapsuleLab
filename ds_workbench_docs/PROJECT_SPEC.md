# Project Spec

## Standard Project Layout

Each workbench project should look like this:

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
tensorflow-cuda
rapids
llm-inference
computer-vision
rag-stack
fastapi-ml-service
fine-tuning-project
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
