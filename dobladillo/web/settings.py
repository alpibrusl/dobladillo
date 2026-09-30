"""The web UI's own preferences, kept out of the scientific record.

An experiment folder, in git, is the record; nothing about how a person likes
the page to behave belongs in it. So preferences live in one small JSON file
on this machine -- `$DOBLADILLO_CONFIG_DIR/web.json`, by default
`~/.config/dobladillo/web.json` -- keyed by the experiment folder's resolved
path. Today there is one: whether an experiment's analyses run by themselves
after each upload or record save. It is off unless someone turns it on.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Final

#: Where the preferences file lives unless DOBLADILLO_CONFIG_DIR says otherwise.
DEFAULT_DIR: Final = Path.home() / ".config" / "dobladillo"


def settings_path() -> Path:
    base = os.environ.get("DOBLADILLO_CONFIG_DIR")
    return (Path(base) if base else DEFAULT_DIR) / "web.json"


class WebSettings:
    """Per-experiment preferences, read and written through one lock."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def auto_analyse(self, folder: Path) -> bool:
        with self._lock:
            entry = self._read().get("experiments", {}).get(str(folder.resolve()), {})
        return bool(entry.get("auto_analyse", False)) if isinstance(entry, dict) else False

    def set_auto_analyse(self, folder: Path, on: bool) -> None:
        with self._lock:
            data = self._read()
            experiments = data.setdefault("experiments", {})
            entry = experiments.setdefault(str(folder.resolve()), {})
            entry["auto_analyse"] = bool(on)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n")
            tmp.replace(self.path)
