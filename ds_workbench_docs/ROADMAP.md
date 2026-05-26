# Roadmap

## Purpose

This roadmap is the current builder guide for CapsuleLab. It starts from what the repo already contains and then names the gaps worth closing next.

CapsuleLab is not trying to become NVIDIA AI Workbench wholesale. The product direction is a local-first workbench for reproducible AI and data-science projects: one portable capsule, one versioned project manifest, Docker-based execution, optional SSH mobility, and a local API/UI that make runtime state visible.

Long term, CapsuleLab should be broader than a runtime manager: it should combine project packaging, app launch, Git workflows, agent workspaces, project knowledge graphs, deployment preparation, and open-source release readiness. The implementation should still grow from the reliable local runtime outward.

The comparison target is NVIDIA AI Workbench as documented in the official user guide updated April 30, 2026. The important patterns to learn from are project portability, location parity, versioned environment configuration, managed applications, Git visibility, secure remote app access, IDE/agent integration, multi-container support, and environment troubleshooting.

## Current NVIDIA AI Workbench Feature Findings

Reviewed against NVIDIA AI Workbench docs on May 25, 2026:

- Managed applications have four documented types: Web App, Process, Compose App, and Native App. Web apps are proxied to local URLs; process apps do not need ports; Compose apps run multi-container stacks; native apps cover local IDEs such as VS Code and Cursor.
- Compose environments support profiles, service healthchecks, shared service-name networking, GPU reservations, and `NVWB_TRIM_PREFIX=true` for proxied web services.
- Remote locations use SSH tunnels for both the Workbench service and reverse proxy. AI Workbench assigns proxy/service port pairs starting at 10000/10001 and persists them per location.
- Web app sharing creates restricted, expiring URLs for a single application on a remote location. It is explicitly for temporary prototype access, not production deployment.
- The CLI covers project/location/environment/application/Git workflows, including clone, publish, pull, push, fetch, commit, history, discard, merge, branch switching, app creation, and Compose file discovery.
- The Build Assistant analyzes failed container builds with restricted repository access. It reads build logs and environment files, writes only build scripts, and requires user review before rebuild.
- Native IDE integrations are project-level app affordances. VS Code and Cursor can attach to a running project container, Cursor gets generated `.cursor/rules/ai-workbench` guidance, and Windsurf uses a manual Dev Containers attach flow.

## Current State

### Implemented Product Surface

- `cap` CLI with commands for init, doctor, build, start, stop, logs, apps, locations, Compose, sync, templates, project inventory, secrets, runs, resources, images, and data metadata.
- FastAPI backend with routes for health, doctor, projects, apps, logs, Compose, locations, Git status, secrets, runs, resources, and image checks.
- React/Vite frontend with project dashboard, project creation, project detail/runtime controls, logs, app controls, compose status/actions, resources, secrets/readiness summaries, and a locations page.
- SQLite state at `~/.capsulelab/capsulelab.db` for registered projects, app state, build metadata, locations, secrets presence, runs, and settings-style local state.
- Pydantic project model with runtime, mounts, caches, datasets, secret references, environment variables, and apps.
- Local Docker single-container runtime with GPU detection, project/app port mapping, app launch through `docker exec`, logs, labels, and ownership checks.
- SSH location support with reachability checks, remote Docker/GPU checks, remote project path conventions, and rsync-based project sync.
- Workbench-style remote tunnel metadata with persistent proxy/service local port pairs and SSH command generation.
- Docker Compose support in CLI and API for detect/status, up, down, logs, and service listing.
- Compose metadata discovery for profiles, service ports, healthchecks, dependencies, GPU intent, and `NVWB_TRIM_PREFIX` web URLs.
- Managed app URL formation with direct local URLs, stable proxy-style URLs, and expiring share-link records for web apps.
- Build Assistant prototype that reads failed build logs plus constrained build-context files and proposes reviewed edits to build scripts without rebuilding automatically.
- Native IDE setup helpers for Cursor, VS Code, and Windsurf that write versioned project guidance and return container attach instructions.
- Git import/scaffold detection plus project Git operations for status, history, branch switching, commit, fetch, pull, push, and publish-to-remote-url.
- Maintained templates: `python-basic`, `pytorch-cuda`, and `streamlit-dashboard`.

### Known Gaps

- CLI, API, and UI are broad enough now that parity needs active protection. New behavior should land in services first, then expose through CLI/API/UI.
- App lifecycle is present and now exposes proxy-style/share URLs, but still needs an actual reverse proxy, shared-access enforcement, stronger health checks, and shared error vocabulary.
- `cap doctor` and `/api/doctor` are useful environment checks, but they are not yet full project reproducibility reports.
- Remote execution depends on SSH and rsync rather than a remote CapsuleLab service. Tunnel port metadata and commands exist, but local/remote parity is not yet as smooth as AI Workbench locations.
- Secrets are stored locally, but the architecture needs an explicit storage/security policy and UI affordances for required/missing secrets.
- Dataset/cache metadata exists, but per-location path mapping and validation are still shallow.
- Git visibility, clone/import scaffolding, and common Git operations exist, but platform-backed publish setup and deep-link workflows are still shallow.
- Compose exists with service metadata discovery, profiles, and web URL hints, but multi-container projects still need template-level conventions, actual health polling, network documentation, and GPU conflict checks.
- The frontend is an operator console, not a full desktop app. CLI/API IDE setup helpers exist, but the UI still lacks one-click Native App launchers, remote app proxying, shared access, build assistant diagnostics, and richer settings.
- Build Assistant parity is partial: local failed-build diagnostics and constrained build-script edit proposals exist, but there is no LLM-backed assistant, endpoint settings, UI review flow, or automated rebuild workflow.
- Project profiles are not yet modeled. Research, deployable, and open-source workflows currently share the same defaults and checks.
- There is no project knowledge graph service yet. Agent support is limited to IDE/setup guidance rather than a full project understanding layer.
- There is no automated doc/test gate that proves templates build, start, expose apps, and satisfy project checks.

## Near-Term Priorities

### 1. Parity And Runtime Reliability

Status: Completed

Goal: make the current feature set dependable before adding another wide surface.

Build:

- A service-first rule for project start/stop/build/status, app lifecycle, Compose, secrets, runs, and resources.
- A shared error model for Docker unavailable, daemon down, permission denied, image missing, bad config, port conflict, GPU requested but unavailable, missing secret, missing dataset, and stale runtime state.
- Tests that cover pure config logic without Docker and mark Docker/SSH/Compose smoke tests separately.
- A parity checklist proving the CLI, API, and UI report the same project/app/container facts.

Acceptance:

```bash
cap doctor
cap init demo --template pytorch-cuda
cd demo
cap build
cap start
cap app list
cap logs
cap stop
```

The same project should show coherent status in the API and UI, with no raw stack traces for expected environment failures.

### 2. Project Reproducibility Report

Status: Completed

Goal: turn `doctor` into the core trust feature.

Build:

- `cap doctor --project` and `/api/projects/{id}/doctor` style output.
- Checks for Docker, GPU, project config, Dockerfile, image metadata, build metadata, app commands, app ports, package files, lockfiles, Git state, dirty files, Git LFS availability, datasets, caches, required secrets, writable outputs, README presence, and template identity.
- A readable report format for CLI and a structured JSON shape for API/UI.
- Severity levels: `ok`, `warning`, `error`, and `info`.

AI Workbench gap closed: versioned environment confidence and visible changes before running work.

### 3. Project Profiles And Template Defaults

Status: Not done

Goal: make `research`, `deployable`, and `opensource` first-class project profiles without creating separate products.

Build:

- Manifest support for `mode` and safe `presets` fields.
- Profile-aware `cap init` template selection and validation.
- Research checks for notebooks, dataset mounts, model cache, experiment tracking, paper notes, run reports, and knowledge graph readiness.
- Deployable checks for Dockerfile, health checks, env validation, tests, secrets scan, deployment manifest, logs, ports, and API tester readiness.
- Open-source checks for README, LICENSE, CONTRIBUTING, examples, docs preview, GitHub templates, package metadata, changelog, and release checklist.
- UI dashboard sections that emphasize the selected profile while keeping shared runtime controls consistent.

Acceptance:

```bash
cap init rag-demo --template research-rag
cap init model-api --template deployable-fastapi
cap init ai-tool --template opensource-python-package
cap doctor --project
```

Each project should report profile-specific readiness without losing the common build/run/apps/logs/Git flow.

### 4. Managed App Lifecycle And URLs

Status: Completed

Goal: make JupyterLab, Streamlit, TensorBoard, MLflow, Gradio, RStudio, and custom apps feel like first-class project tools.

Build:

- Strong app status based on PID, port, healthcheck, log path, and recent exit state.
- Stale state cleanup when containers restart.
- App URL formation that works consistently for local and SSH locations.
- Optional local reverse proxy design so app URLs can be stable and remote ports do not leak into user workflows.
- Temporary app sharing with expiration, restricted app scope, and eventual browser/session binding.
- UI controls for app start/stop/logs/status that map exactly to API facts.

AI Workbench gap closed: managed applications surfaced by the workbench rather than ad hoc commands.

### 5. Remote Location V1

Status: Completed

Goal: make SSH locations honest, repeatable, and useful without adding a remote agent yet.

Build:

- Location status that reports SSH reachability, Docker, GPU, project root, disk space, and remote CapsuleLab assumptions.
- Persistent proxy/service tunnel port assignment starting at 10000/10001, with visible SSH tunnel commands.
- `cap sync rsync` hardening with ignore rules, dry-run detail, and clear failure messages.
- Remote start/stop/logs/app URL rules documented and tested.
- Per-location dataset/cache/secret mapping.
- UI visibility for location status and project availability.

AI Workbench gap partially closed: locations and project mobility. CapsuleLab should remain clear that this is SSH-plus-Docker, not a full remote service tunnel.

### 6. Git Import And Project Inventory

Status: Completed

Goal: let users bring existing repos into CapsuleLab without manual setup.

Build:

- `cap project import <path-or-url>` or `cap clone <url>`.
- Scaffold `.workbench/project.yaml` when missing.
- Detect Dockerfile, Compose files, requirements, pyproject, notebooks, common app files, and GPU intent.
- Register, repair, and unregister project inventory cleanly.
- Show Git branch, remote, dirty file count, LFS availability, history, branches, commit, fetch, pull, push, and publish readiness in CLI/API/UI.
- Add platform-aware publish helpers for GitHub, GitLab, and self-hosted GitLab once authentication is designed.

AI Workbench gap closed: managed Git repository workflows and import of existing projects.

### 7. Secrets, Datasets, Caches, And Per-Location Overrides

Status: Completed

Goal: separate versioned project intent from machine-specific values.

Build:

- Explicit local secret storage policy and migration path if storage changes.
- Required secret declarations in `.workbench/project.yaml` with values stored outside the repo.
- Dataset declarations with read-only defaults, empty/missing path checks, and per-location source path overrides.
- Cache presets for Hugging Face, PyTorch, pip, uv, npm, model-serving runtimes, and app-specific caches.
- UI for missing secrets and missing datasets without exposing secret values.

AI Workbench gap closed: host-specific runtime config, environment variables, mounts, and sensitive values.

### 8. Compose And Multi-Service Projects

Status: Completed

Goal: make multi-container projects a supported path, not a side command.

Build:

- Compose status in the same project status model as the single-container runtime.
- Service health, ports, logs, and app URL discovery.
- Compose profile selection and static validation for proxied web services.
- Template conventions for RAG, MLflow plus database, model-server plus frontend, and app-plus-worker systems.
- Clear distinction between the project container and sidecar/stack services.

AI Workbench gap closed: Compose stack support for full-stack AI systems.

### 9. IDE And Agent Integration

Status: Completed

Goal: support real development inside the project container.

Build:

- `cap shell`, `cap exec`, and `cap attach` flows that make the project container the default development boundary.
- VS Code/Cursor/Windsurf attach helpers.
- Generated Cursor/Windsurf project rules and VS Code extension recommendations.
- Documented agent sandbox pattern with mounted project, controlled environment, secrets handling, and Git visibility.
- Optional template for coding-agent-ready projects.

AI Workbench gap closed: IDEs and AI coding agents scoped to the project container.

### 10. Knowledge Graph And Agent Workspace

Status: Not done

Goal: make CapsuleLab agent-native without letting agents blur project boundaries.

Build:

- Project knowledge graph index for code, notebooks, papers, configs, templates, runs, apps, and docs.
- Agent-readable project summaries that explain architecture, setup, apps, data/model mounts, recent runs, and known checks.
- Research-specific paper/source graph and experiment explanation flow.
- Open-source project explanation generator for README/docs/release preparation.
- Reviewed agent action model for edits, build fixes, benchmark interpretation, and report generation.
- Local storage policy for graph indexes and agent scratch state.

Acceptance:

An agent should be able to answer "what is this capsule, how do I run it, what changed between runs, and what should I fix before sharing or deploying it?" using local project context.

### 11. Build Diagnostics And BYOC

Status: Completed

Goal: make failed builds fixable and custom images safe to use.

Build:

- Build log capture and failure summary in CLI/API/UI.
- `cap build-assistant` and `/api/projects/{id}/build/assistant` for constrained failed-build analysis.
- BYOC checks for image availability, GPU compatibility, Python/Jupyter readiness, workspace path, and app command compatibility.
- Build scripts and package-file conventions.
- Optional LLM-backed build assistant later, after local diagnostics and review workflows are stable.

AI Workbench gap partially closed: build assistant and custom base image workflows.

## Template Roadmap

Keep the default catalog small until validation is automated.

Maintained now:

- `python-basic`: Completed
- `pytorch-cuda`: Completed
- `streamlit-dashboard`: Completed

Add next only after template validation exists:

- `research-rag`: Not done - notebooks, retrieval stack, evaluation runs, source notes, and graph-ready paper/context layout.
- `research-pytorch`: Not done - training notebook, model cache, TensorBoard, experiment logging, and reproducibility report.
- `research-model-eval`: Not done - benchmark harness, model comparison dashboard, and run-diff output.
- `deployable-fastapi`: Not done - model API, health checks, tests, Dockerfile, API tester, and deployment manifest.
- `deployable-gradio`: Not done - demo app packaged with logs, env validation, and release checklist.
- `deployable-batch-inference`: Not done - scripts, configs, sample inputs, output mounts, and runtime logs.
- `opensource-python-package`: Not done - README/license/contributing/docs/examples/package metadata and CI template.
- `opensource-ai-demo`: Not done - public demo repo with app launcher, screenshots/assets, examples, and release checklist.
- `agent-sandbox`: Not done - IDE/agent-ready project container with Git visibility and conservative permissions.

Every template must include:

- Dockerfile or Compose file
- `.workbench/project.yaml` now, with a `capsule.yaml` migration path later
- README
- package files
- at least one useful app or notebook
- `cap doctor` expectations
- build/start/app smoke path
- declared profile and profile-specific checks

## Later Backlog

### App Networking & Sharing
Status: Not done

- Stable app reverse proxy for consistent local/remote app URLs
- Optional shared app URLs for collaboration within trusted networks
- App authentication mechanisms for shared access
- Browser/session binding for share URLs and cleanup of expired shares

### Container Registry Workflows
Status: Not done

- Documentation for NGC, Hugging Face, GitHub Container Registry, GitLab Container Registry, and Docker Hub workflows
- Private registry authentication and credential management
- Image signing and verification for enhanced security

### Remote Execution Enhancements
Status: Not done

- Cloud GPU location adapters (AWS, GCP, Azure) after SSH locations are reliable
- Tailscale-style remote guidance for secure mesh networking
- Remote agent option for improved performance over pure SSH

### Project Collaboration & Distribution
Status: Completed

- Project publish/deep-link flows for sharing workbench projects
- Project templating system for organizational reuse
- Export/import functionality for project snapshots

### Model & Data Management
Status: Not done

- Local model registry with versioning and metadata tracking
- Model download integrity checks and caching
- Dataset versioning integration with project Git history

### Observability & Monitoring
Status: Completed

- Rich resource dashboard with historical trends for CPU, memory, GPU, VRAM, disk usage
- Container and app-level resource consumption tracking
- Compose service health metrics and dependency visualization

### Configuration & Extensibility
Status: Not done

- Settings UI for runtime preferences, Docker/Podman selection, certificates, and default paths
- Plugin architecture for extending workbench functionality
- Custom dashboard widgets and panels

### Data Migration & Evolution
Status: Not done

- Migration system for SQLite once local state changes become incompatible
- Config schema versioning and automatic migration
- Backup/restore functionality for workbench metadata
