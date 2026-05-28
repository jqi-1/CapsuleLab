import json
from pathlib import Path
from typing import Any


class DocumentStore:
    """Thin JSON document persistence.

    Handles read/write/delete of a JSON document at ``path`` with
    consistent error handling (missing → default, decode errors → raise).
    """

    def __init__(self, path: str | Path, default: Any = None):
        self._path = Path(path)
        self._default = default if default is not None else {}

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> Any:
        if not self._path.exists():
            return self._default
        return json.loads(self._path.read_text())

    def write(self, data: Any) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, default=str))

    def delete(self) -> bool:
        if self._path.exists():
            self._path.unlink()
            return True
        return False

    def update(self, updater: Any) -> Any:
        """Read, apply *updater* (callable or dict), write, return result.

        If *updater* is callable::

            store.update(lambda data: {**data, "key": "val"})

        If *updater* is a dict::

            store.update({"key": "val"})
        """
        data = self.read()
        if callable(updater):
            data = updater(data)
        elif isinstance(updater, dict):
            if isinstance(data, dict):
                data.update(updater)
            else:
                data = updater
        self.write(data)
        return data
