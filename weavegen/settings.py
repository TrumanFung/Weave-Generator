"""Remembered preferences: a small JSON file in the user's settings folder.

Nothing here imports Tkinter. A missing, unreadable or damaged file just means the defaults are
used, and every value is checked on the way in, so a hand-edited file cannot break the program.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

MAX_RECENT = 8
CONFIG_DIR_ENV = "WEAVEGEN_CONFIG_DIR"  # overrides the settings folder (used by the tests)

_GEOMETRY = re.compile(r"^\d{3,5}x\d{3,5}([+-]-?\d{1,5}){0,2}$")


def settings_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "WeaveGenerator"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "weavegen"


def settings_path() -> Path:
    return settings_dir() / "settings.json"


def _int_between(low: int, high: int) -> Callable[[Any], int]:
    def check(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError
        return value
    return check


def _one_of(*options: str) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        if value not in options:
            raise ValueError
        return value
    return check


def _geometry(value: Any) -> str:
    if value != "" and not (isinstance(value, str) and _GEOMETRY.match(value)):
        raise ValueError
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError
    return value


def _recent(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError
    seen: list[str] = []
    for item in value:
        if isinstance(item, str) and item and item not in seen:
            seen.append(item)
    return seen[:MAX_RECENT]


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError
    return dict(value)


# name -> (default, checker). A checker returns the clean value or raises ValueError.
SPEC: dict[str, tuple[Any, Callable[[Any], Any]]] = {
    "zoom": (16, _int_between(4, 40)),
    "view": ("drawdown", _one_of("drawdown", "cloth")),
    "yarn_width": (85, _int_between(30, 100)),
    "float_limit": (3, _int_between(1, 400)),
    "float_side": ("both", _one_of("both", "face", "back")),
    "page_size": ("a4", _one_of("a4", "letter")),
    "window": ("", _geometry),
    "last_directory": ("", _text),
    "recent_files": ([], _recent),
    "yardage": ({}, _string_map),
}


class Settings:
    """The preferences, held in memory and written back with save()."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else settings_path()
        self.values: dict[str, Any] = {key: _fresh(default) for key, (default, _c) in SPEC.items()}

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        settings = cls(path)
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings
        if isinstance(raw, dict):
            for key in SPEC:
                if key in raw:
                    settings.set(key, raw[key])
        return settings

    def get(self, key: str) -> Any:
        return _fresh(self.values[key])

    def set(self, key: str, value: Any) -> bool:
        """Store a value; one that fails its check is ignored (and False comes back)."""
        if key not in SPEC:
            raise KeyError(key)
        try:
            self.values[key] = SPEC[key][1](value)
        except (ValueError, TypeError):
            return False
        return True

    # ---- recent files ----
    def add_recent(self, path: str | Path) -> None:
        path = str(path)
        self.values["recent_files"] = _recent([path] + [p for p in self.values["recent_files"] if p != path])

    def forget_recent(self, path: str | Path) -> None:
        self.values["recent_files"] = [p for p in self.values["recent_files"] if p != str(path)]

    def clear_recent(self) -> None:
        self.values["recent_files"] = []

    def save(self) -> bool:
        """Write the file (replacing it in one step). A folder that cannot be written is not an error."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix="settings_", suffix=".tmp")
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as out:
                    json.dump(self.values, out, indent=2)
                os.replace(temp, self.path)
            except BaseException:
                try:
                    os.remove(temp)
                except OSError:
                    pass
                raise
        except OSError:
            return False
        return True


def _fresh(value: Any) -> Any:
    """A copy, so callers cannot change the stored list or dict by accident."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value
