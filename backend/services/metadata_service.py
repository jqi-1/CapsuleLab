import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.db import sqlite


BACKUP_VERSION = 1
BACKUP_TABLES = [
    "projects",
    "app_runtime_state",
    "locations",
    "settings",
    "experiment_runs",
    "build_metadata",
    "build_logs",
    "app_shares",
    "location_tunnels",
    "location_overrides",
    "resource_snapshots",
    "container_resources",
    "app_resources",
    "compose_service_resources",
]
SECRET_TABLES = ["secrets"]


def create_backup(output_path: str, include_secrets: bool = False) -> dict:
    sqlite.init_db()
    tables = BACKUP_TABLES + (SECRET_TABLES if include_secrets else [])
    backup = {
        "backup_version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "include_secrets": include_secrets,
        "tables": {},
    }
    with sqlite.get_db() as conn:
        for table in tables:
            backup["tables"][table] = _rows(conn, table)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(backup, indent=2))
    return {
        "path": str(path),
        "backup_version": BACKUP_VERSION,
        "include_secrets": include_secrets,
        "tables": {table: len(rows) for table, rows in backup["tables"].items()},
    }


def inspect_backup(path: str) -> dict:
    backup = _load_backup(path)
    return {
        "backup_version": backup.get("backup_version"),
        "created_at": backup.get("created_at"),
        "include_secrets": backup.get("include_secrets", False),
        "tables": {table: len(rows) for table, rows in (backup.get("tables") or {}).items()},
    }


def restore_backup(path: str, include_secrets: bool = False) -> dict:
    backup = _load_backup(path)
    if backup.get("backup_version") != BACKUP_VERSION:
        raise ValueError(f"Unsupported backup_version {backup.get('backup_version')}")
    sqlite.init_db()
    tables = [table for table in BACKUP_TABLES if table in backup.get("tables", {})]
    if include_secrets and "secrets" in backup.get("tables", {}):
        tables.append("secrets")
    restored: dict[str, int] = {}
    with sqlite.get_db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in reversed(tables):
            conn.execute(f"DELETE FROM {table}")
        for table in tables:
            rows = backup["tables"].get(table, [])
            for row in rows:
                _insert_row(conn, table, row)
            restored[table] = len(rows)
        conn.execute("PRAGMA foreign_keys=ON")
    return {
        "path": str(Path(path)),
        "restored": restored,
        "secrets_restored": include_secrets and "secrets" in restored,
    }


def _load_backup(path: str) -> dict:
    backup_path = Path(path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {path}")
    data = json.loads(backup_path.read_text())
    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError("Invalid CapsuleLab metadata backup")
    return data


def _rows(conn, table: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]


def _insert_row(conn, table: str, row: dict[str, Any]) -> None:
    if not row:
        return
    columns = list(row.keys())
    placeholders = ", ".join("?" for _ in columns)
    names = ", ".join(columns)
    conn.execute(
        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
        tuple(row[column] for column in columns),
    )
