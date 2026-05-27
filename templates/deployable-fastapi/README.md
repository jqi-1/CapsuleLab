# Deployable FastAPI Project

Model API with health checks, tests, and deployment readiness.

## Quick Start

```bash
cap doctor
cap build
cap start
cap app start fastapi
cap app open fastapi
```

## Apps

- **FastAPI** — model API server at port 8000

## Project Structure

```
app/             — FastAPI application code
src/             — reusable source code
tests/           — test suite
configs/         — configuration files
docker/          — Docker-related assets
deploy/          — reviewed deployment manifest starter
docs/            — API and logging notes
scripts/         — API smoke test and local secret scan
data/            — datasets (gitignored)
models/          — model artifacts (gitignored)
```

## Deployment Readiness

Run the API smoke test after the app starts:

```bash
python scripts/check_api.py
```

Review `deploy/deployment.yaml` before using it in a real cluster. It is a starter manifest, not a production policy.
