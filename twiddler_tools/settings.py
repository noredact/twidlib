"""Persist app preferences and the last-imported config."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_dir

from . import cfg_io
from .csv_io import load_csv
from .model import Config


def state_path() -> Path:
    return Path(user_data_dir("twiddler-tools")) / "state.json"


def _load_state() -> dict:
    p = state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(patch: dict) -> None:
    state = _load_state()
    state.update(patch)
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state), encoding="utf-8")


def save_last_config(path: str, kind: str) -> None:
    """Remember the last imported config file (kind is "csv" or "cfg")."""
    _save_state({"last_config": {"path": path, "kind": kind}})


def load_last_config() -> tuple[Config, bytes | None]:
    """Return (config, base_cfg_bytes) for the last imported file.

    base_cfg_bytes is non-None when the last import was a .cfg, so the Export
    Queue tab can use it as the export base without prompting. Returns an
    empty config if nothing was imported yet or the file is no longer readable.
    """
    entry = _load_state().get("last_config")
    if not entry:
        return Config(bindings=[], source=""), None
    try:
        path = entry["path"]
        kind = entry.get("kind", "csv")
        if kind == "cfg":
            raw = Path(path).read_bytes()
            parsed = cfg_io.parse_cfg(raw)
            return cfg_io.cfg_to_config(parsed, source=path), raw
        return load_csv(path), None
    except Exception:
        return Config(bindings=[], source=""), None


def save_gui_scale(factor: float) -> None:
    _save_state({"gui_scale": factor})


def load_gui_scale() -> float:
    value = _load_state().get("gui_scale", 1.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0


def save_last_app(name: str) -> None:
    """Remember the last-used app tab."""
    _save_state({"last_app": name})


def load_last_app() -> str:
    """Return the last-used app tab, defaulting to Chord Lookup."""
    value = _load_state().get("last_app", "Chord Lookup")
    return value if isinstance(value, str) else "Chord Lookup"
