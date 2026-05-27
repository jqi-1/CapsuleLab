import json
from typing import Any

from backend.db.sqlite import get_db, init_db


DEFAULT_SETTINGS = {
    "runtime.default": "docker",
    "paths.default_project_root": "",
    "proxy.base_url": "http://localhost:10000",
    "certificates.bundle": "",
}
ALLOWED_SETTINGS = {
    "runtime.default",
    "paths.default_project_root",
    "proxy.base_url",
    "certificates.bundle",
}


def list_settings(include_defaults: bool = True) -> dict[str, Any]:
    init_db()
    values = dict(DEFAULT_SETTINGS) if include_defaults else {}
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    for row in rows:
        values[row["key"]] = _decode(row["value"])
    return values


def set_setting(key: str, value: Any) -> dict:
    if key not in ALLOWED_SETTINGS:
        raise ValueError(f"Unsupported setting '{key}'")
    init_db()
    encoded = json.dumps(value)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, encoded),
        )
    return {"key": key, "value": value}


def get_setting(key: str) -> Any:
    if key not in ALLOWED_SETTINGS:
        raise ValueError(f"Unsupported setting '{key}'")
    return list_settings().get(key)


def remove_setting(key: str) -> bool:
    init_db()
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        return cursor.rowcount > 0


def _decode(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value
