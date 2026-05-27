# ADR-0001: RuntimeAdapter Seam for Container Lifecycle

**Status:** Accepted
**Date:** 2026-05-26

## Context

CapsuleLab runs project containers on both local Docker and remote SSH hosts (Locations). In the current code:

- Local operations call `docker_service.*` directly (subprocess Docker commands).
- Remote operations call `ssh_service.*` which SSH-tunnels Docker commands.
- The API router `projects.py:start_project` orchestrates the local path inline with config loading, mount resolution, and port checks.

This creates two problems:

1. **Duplicated orchestration** — the start/stop/status flow is implemented once in the API router (local) and implied in CLI commands that call ssh_service directly. There is no single module to test for lifecycle correctness.
2. **No seam for testing** — local operations cannot be verified without a real Docker daemon; remote operations cannot be verified without an SSH target.

## Decision

Introduce a `RuntimeAdapter` interface that abstracts container operations. Two concrete adapters implement it:

| Adapter | Backend | Operations |
|---------|---------|------------|
| `LocalDockerAdapter` | `subprocess.run(["docker", ...])` | run, stop, exec, logs, is_running, container_exists, inspect |
| `RemoteSSHAdapter` | `ssh_service.*` (SSH-tunneled Docker) | same operations piped via SSH |

A `RuntimeManager` class accepts a `RuntimeAdapter` via constructor injection and owns the lifecycle logic (start, stop, status). The API router and CLI both go through `RuntimeManager`.

## Consequences

**Positive:**
- Lifecycle logic lives in one place (`RuntimeManager`), not split across router + services.
- Tests inject `FakeRuntimeAdapter` — no Docker/SSH required.
- Adding a new runtime backend (e.g., Kubernetes podman) means writing a third adapter, not changing the manager.

**Negative:**
- The adapter interface must stay generic enough to cover both local and remote semantics. Things like "port conflict detection" are local-specific optimizations that leak into the adapter contract.
- Slightly more ceremony than calling `docker_service.*` directly.

## Rejected Alternatives

- **Keep separate code paths** — rejected because it perpetuates the current state where neither path is testable in isolation and the orchestration logic is duplicated.

## Compliance

All `start`/`stop`/`status` entry points must go through `RuntimeManager`, not call adapters directly. The API router and CLI are the enforcement boundary.
