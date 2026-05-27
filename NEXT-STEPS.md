# NEXT-STEPS.md — CapsuleLab Cleanup & Stabilization

## Priority 0: Repo Hygiene (do first)

- [ ] **Remove `.venv` and `capsulelab.egg-info` from Git tracking**
  - `git rm -r --cached .venv capsulelab.egg-info`
- [ ] **Update `.gitignore`** — add `.venv/`, `.env`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.egg`, `*.pyc`, coverage files
- [ ] **Rename frontend package** — `frontend/package.json`: `"name": "@capsulelab/frontend"`, `"version": "0.1.0"`

## Priority 1: Dependency Correctness

- [ ] **Sync `requirements.txt` with `setup.py`** — add `fastapi>=0.109.0`, `uvicorn>=0.27.0`
- [ ] **Add `pyproject.toml`** with optional-dependencies groups:
  ```toml
  [project.optional-dependencies]
  api = ["fastapi", "uvicorn[standard]"]
  dev = ["pytest", "ruff", "mypy"]
  ```
- [ ] Remove `setup.py` in favor of `pyproject.toml` (or keep both but keep deps in sync)

## Priority 2: Security Defaults

- [ ] **Lock down CORS** — change `backend/main.py`:
  ```python
  allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"]
  allow_credentials=False
  ```
- [ ] **Add API Settings class** — `backend/config.py` with `Pydantic BaseSettings` for CORS origins, host, port, debug mode
- [ ] **Bind API to localhost by default** — README should document `--host 127.0.0.1`, not `0.0.0.0`
- [ ] Add security model section to README

## Priority 3: README & Product Credibility

- [ ] **Add `## Status` section to README** distinguishing working vs experimental vs planned
  - Working: `cap init`, `cap doctor`, basic Docker build/start/stop, template creation, FastAPI health, React shell
  - Experimental: SSH locations, app launchers, run tracking, image registry, knowledge graph
  - Planned: agent orchestrator dashboard, project knowledge graph UI, deployment mode automation
- [ ] **Replace `frontend/README.md`** — remove default Vite template docs, add CapsuleLab frontend setup

## Priority 4: CI & Quality

- [ ] **Add GitHub Actions workflow** (`.github/workflows/ci.yml`):
  - pytest (non-Docker, non-SSH) on every push
  - ruff lint / format check
- [ ] Add `ruff` config (`pyproject.toml` or `ruff.toml`)
- [ ] Consider switching to `pyproject.toml` for modern packaging

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

1. Clean Git tracking (`.venv`, `*.egg-info`) + update `.gitignore`
2. Sync `requirements.txt` + add `fastapi`/`uvicorn`
3. Lock down CORS
4. Update `frontend/package.json` name
5. Replace `frontend/README.md`
6. Add `## Status` section to root `README.md`
7. Add GitHub Actions CI
8. Rename `requirements.txt` → `pyproject.toml` (if desired)
