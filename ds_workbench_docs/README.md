# CapsuleLab Planning Docs

This folder contains a condensed design pack for CapsuleLab, a local-first AI and data-science workbench for packaging, running, deploying, and understanding reproducible projects.

## Files

- `AGENTS.md` — instructions for coding agents working on the project
- `ARCHITECTURE.md` — system architecture and module breakdown
- `ROADMAP.md` — phased implementation plan
- `PROJECT_SPEC.md` — proposed project file layout and YAML config schema

## Product Summary

CapsuleLab should let users package an AI/data-science project into a portable capsule: code, environment, apps, data mounts, model config, secrets, runs, agents, and project knowledge.

The product is inspired by NVIDIA AI Workbench's category and workflow model, but should keep a distinct identity: different visual language, backend, config format, schema, templates, and agent-native features. The goal is not a pixel clone. The target workflow remains:

```txt
Project -> Environment -> Build -> Run -> Apps -> Logs -> Git -> Remote Machine
```

The main goal is to make one capsule portable across:

- local laptop
- gaming PC
- DGX Spark
- remote server
- cloud GPU machine

The near-term product should still focus on dependable Docker-based local execution, app launching, Git visibility, and a simple CLI/API/UI loop before adding advanced remote execution. The long-term product should expand into an agent-assisted research and deployment workbench with project knowledge graphs and orchestrator-style dashboards.

## Project Profiles

CapsuleLab projects should support three profiles that tune defaults, templates, dashboards, and validation checks without splitting the product:

- `research`: notebooks, experiments, datasets, model comparison, paper notes, run reports, and knowledge graphs.
- `deployable`: APIs, containerized apps, health checks, test coverage, env validation, logs, and deployment checklists.
- `opensource`: README/license/contributing checks, docs preview, examples, package metadata, GitHub templates, and release readiness.

Profiles should guide setup and review. They should not create incompatible project types.

## Distribution Assumption

This app is intended for personal, local use. It is not expected to be deployed as a hosted service.

It may eventually be published on GitHub as an open-source project, but the product should still assume local installation, local data, local credentials, and local control. Do not optimize early for SaaS deployment, account systems, hosted billing, multi-tenant permissions, or production operations.

## Product Review Notes

The strongest product wedge is not "another notebook launcher." It is a local-first project runtime manager that remembers the setup ritual for a data-science project and makes that ritual portable across machines.

The first version should make this moment feel effortless:

```bash
cap init demo --template pytorch-cuda
cd demo
cap doctor
cap build
cap start
cap app start jupyter
cap app open jupyter
```

Main concerns:

- The project can become too broad if it tries to match a full platform too early.
- The UI should not arrive before the CLI and runtime model are reliable.
- App lifecycle management is harder than launching `docker exec -d`; the workbench must know whether apps are alive, where their logs are, and how to stop them.
- Template maintenance can become expensive. Start with a few excellent templates before adding many specialized ones.
- Reproducibility checks are part of the product value, not just a late polish feature.
- Agent and knowledge-graph features should make projects easier to understand and improve, but should stay scoped to the capsule boundary and avoid turning the local app into a hosted SaaS platform.

Suggested early focus:

- Make local Docker execution boringly dependable.
- Keep the current `.workbench/project.yaml` reliable, while designing the eventual public capsule contract around `capsule.yaml`.
- Add `cap doctor` early.
- Track app runtime state explicitly.
- Delay remote agents, Kubernetes, hosted accounts, and broad template catalogs.
