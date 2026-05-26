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
data/            — datasets (gitignored)
models/          — model artifacts (gitignored)
```
