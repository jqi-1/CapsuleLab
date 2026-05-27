# CapsuleLab Domain Language

## Core domain

- **Project** — a code project with a `.workbench/project.yaml` config defining its runtime, mounts, datasets, apps, secrets, and environment. The primary aggregate root.
- **Runtime** — Docker (or Podman, Compose) container that executes the project's code.
- **App** — a process running inside the container (Jupyter, Streamlit, Gradio, etc.). Defined in `ProjectConfig.apps`.
- **Location** — a remote SSH host where projects can be deployed and run.
- **Build** — a Docker image build from the project's Dockerfile.
- **Experiment Run** — a tracked execution of experiment code, with artifacts and notes.

## Support domain

- **Mount / Cache / Dataset / Secret** — resources attached to a container. Location-aware overrides exist for per-location path resolution.
- **Resource Snapshot** — a point-in-time record of CPU, memory, and disk usage for a project, its containers, apps, and compose services.

## Architecture vocabulary

- **Repository** — a module that encapsulates persistence for one aggregate root. Exposes a focused interface (2–5 methods). Testable against an in-memory SQLite. No direct SQLite imports outside repositories.
- **Repository list**: `ProjectsRepository`, `AppsRepository`, `SecretsRepository`, `BuildsRepository`, `RunsRepository`, `LocationsRepository`, `ResourcesRepository`, `SharesRepository`.
- **Callers import repos directly** — no Database facade.
- **RuntimeManager** — module that owns the project container lifecycle (start, stop, status). Accepts a `RuntimeAdapter` seam via constructor injection.
- **RuntimeAdapter** — seam interface for executing container operations. Two adapters: `LocalDockerAdapter` (subprocess docker commands) and `RemoteSSHAdapter` (SSH-tunneled docker commands).
- **MountResolver** — module that resolves `ProjectConfig` mounts/caches/datasets into Docker volume tuples. Accepts an optional location ID for per-location overrides.
- **ResourceMonitor** — class that gathers current system resources (CPU, memory, disk, GPU, project disk usage). Accepts injectable sensor functions for testability.
