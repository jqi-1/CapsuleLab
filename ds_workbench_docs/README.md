# Data-Science Workbench Planning Docs

This folder contains a condensed design pack for building a local-first data-science and AI workbench.

## Files

- `AGENTS.md` — instructions for coding agents working on the project
- `ARCHITECTURE.md` — system architecture and module breakdown
- `ROADMAP.md` — phased implementation plan
- `PROJECT_SPEC.md` — proposed project file layout and YAML config schema

## Product Summary

The workbench should manage reproducible, containerized data-science and AI projects.

The main goal is to make one project portable across:

- local laptop
- gaming PC
- DGX Spark
- remote server
- cloud GPU machine

The MVP should focus on Docker-based local execution, app launching, and a simple CLI before adding a full UI or advanced remote execution.

## Distribution Assumption

This app is intended for personal, local use. It is not expected to be deployed as a hosted service.

It may eventually be published on GitHub as an open-source project, but the product should still assume local installation, local data, local credentials, and local control. Do not optimize early for SaaS deployment, account systems, hosted billing, multi-tenant permissions, or production operations.

## Product Review Notes

The strongest product wedge is not "another notebook launcher." It is a local-first project runtime manager that remembers the setup ritual for a data-science project and makes that ritual portable across machines.

The first version should make this moment feel effortless:

```bash
wb init demo --template pytorch-cuda
cd demo
wb doctor
wb build
wb start
wb app start jupyter
wb app open jupyter
```

Main concerns:

- The project can become too broad if it tries to match a full platform too early.
- The UI should not arrive before the CLI and runtime model are reliable.
- App lifecycle management is harder than launching `docker exec -d`; the workbench must know whether apps are alive, where their logs are, and how to stop them.
- Template maintenance can become expensive. Start with a few excellent templates before adding many specialized ones.
- Reproducibility checks are part of the product value, not just a late polish feature.

Suggested early focus:

- Make local Docker execution boringly dependable.
- Keep `.workbench/project.yaml` as the source of truth.
- Add `wb doctor` early.
- Track app runtime state explicitly.
- Delay remote agents, Kubernetes, hosted accounts, and broad template catalogs.
