# NEXT-STEPS.md — CapsuleLab Cleanup & Stabilization

## Priority 0: Repo Hygiene (do first)

- [x] **Remove `.venv` and `capsulelab.egg-info` from Git tracking**
  - `git rm -r --cached .venv capsulelab.egg-info`
- [x] **Update `.gitignore`** — add `.venv/`, `.env`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.egg`, `*.pyc`, coverage files
- [x] **Rename frontend package** — `frontend/package.json`: `"name": "@capsulelab/frontend"`, `"version": "0.1.0"`

## Priority 1: Dependency Correctness

- [x] **Sync `requirements.txt` with `setup.py`** — `fastapi>=0.109.0`, `uvicorn>=0.27.0` present in both
- [x] **Add `pyproject.toml`** with optional-dependencies groups:
  ```toml
  [project.optional-dependencies]
  api = ["fastapi>=0.109.0", "uvicorn[standard]>=0.27.0"]
  dev = ["pytest>=8.0", "ruff>=0.6.0", "mypy>=1.10"]
  ```
- [x] **Remove `setup.py`** — all packaging metadata lives in `pyproject.toml`

## Priority 2: Security Defaults

- [x] **Lock down CORS** — `backend/main.py` uses `app_settings.cors_origins` (defaults to `localhost:5173`, `127.0.0.1:5173`) with `allow_credentials=False`
- [x] **Add API Settings class** — `backend/config.py` with `Pydantic BaseSettings` for `cors_origins`, `host`, `port`, `debug`
- [x] **Bind API to localhost by default** — config defaults to `127.0.0.1`; README documents `--host 127.0.0.1`
- [x] **Add security model section to README** — `## Security Model` section exists at line 205

## Priority 3: README & Product Credibility

- [x] **Add `## Status` section to README** with working / experimental / planned breakdown
  - Working: `cap init`, `cap doctor`, basic Docker build/start/stop, template creation, FastAPI health, React shell
  - Experimental: SSH locations, app launchers, run tracking, image registry, knowledge graph
  - Planned: agent orchestrator dashboard, project knowledge graph UI, deployment mode automation
- [x] **Replace `frontend/README.md`** — now has CapsuleLab frontend setup with React + TypeScript + Tailwind

## Priority 4: CI & Quality

- [x] **Add GitHub Actions workflow** (`.github/workflows/ci.yml`)
  - pytest (non-Docker, non-SSH) on every push
  - ruff lint / format check
- [x] **Add `ruff` config** — `ruff.toml` exists; also embedded in `pyproject.toml`
- [x] **Switch to `pyproject.toml`** — done with build config, optional-deps, and tool config

## Priority 5: Architecture (medium-term)

- [ ] **Extract shared business logic** into `capsulelab/` package:
  ```
  capsulelab/
    core/
      config.py
      errors.py
      paths.py
    services/
      docker.py
      projects.py
      templates.py
      runtime.py
  ```
- [ ] Both CLI and API import from `capsulelab.*` instead of `backend.*`
- [ ] Refactor `backend/main.py` to be a thin API adapter over `capsulelab` services

## Implementation Order

- [x] Clean Git tracking (`.venv`, `*.egg-info`) + update `.gitignore`
- [x] Sync `requirements.txt` + add `fastapi`/`uvicorn`
- [x] Lock down CORS
- [x] Update `frontend/package.json` name
- [x] Replace `frontend/README.md`
- [x] Add `## Status` section to root `README.md`
- [x] Add GitHub Actions CI
- [x] Rename `requirements.txt` → `pyproject.toml` (keep `setup.py` for now)
- [ ] **Remove `setup.py`** (last remaining cleanup item)
