"""Twiddler 4 tooling core.

The canonical data model and CSV I/O live here; the PySide6 GUI imports these
modules. GUI code is deliberately not imported from this package so the core
can be used and tested without Qt installed.
"""

from .model import (
    Action,
    ActionKind,
    Binding,
    Chord,
    Config,
    FingerKey,
    KeySegment,
    ModSegment,
    PendingChord,
    TextSegment,
    ThumbKey,
    expand_finger_token,
    format_chord,
    parse_action,
    parse_chord_spec,
    parse_finger_tokens,
)
from .csv_io import parse_csv, render_csv
from .lookup import find_by_chord, find_by_text
from .json_io import (
    chord_to_code,
    code_to_chord,
    config_to_custom_json,
    render_custom_json,
)

__all__ = [
    "Action",
    "ActionKind",
    "Binding",
    "Chord",
    "Config",
    "FingerKey",
    "KeySegment",
    "ModSegment",
    "PendingChord",
    "TextSegment",
    "ThumbKey",
    "expand_finger_token",
    "format_chord",
    "parse_action",
    "parse_chord_spec",
    "parse_finger_tokens",
    "parse_csv",
    "render_csv",
    "find_by_chord",
    "find_by_text",
    "chord_to_code",
    "code_to_chord",
    "config_to_custom_json",
    "render_custom_json",
]
