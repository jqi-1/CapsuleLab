# API Notes

## Local Smoke Test

```bash
cap build
cap start
cap app start fastapi
python scripts/check_api.py
```

## Endpoints

- `GET /health` returns runtime health.
- `GET /` returns a small service descriptor.

## Logs

The FastAPI app writes server logs to stdout inside the project container. Use:

```bash
cap app logs fastapi
```
