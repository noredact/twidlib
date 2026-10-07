"""Export a config to the tuner's custom-mapping JSON format.

Grounded in the repo-root file
'twiddler_cfg_mirrorwalk_nomcc_twiddler_as_V5_as_V7.json'.

Chord code format:
  * Thumbs: an optional 'T<digits>+' prefix (digits from 0-4), omitted when no
    thumb keys are pressed.
  * Fingers: four characters, one per row (rows 1-4 in order). Each character
    is 'L'/'M'/'R' (the column pressed) or 'O' (no key in that row).

The format cannot represent chords with more than one column pressed in the
same row (e.g. '1LM'), nor mouse-row keys, nor system actions; those bindings
are reported as skipped.
"""

from __future__ import annotations

import json

from .model import (
    FINGER_COLS,
    FINGER_ROWS,
    ActionKind,
    Binding,
    Chord,
    Config,
    FingerKey,
    ThumbKey,
)


def chord_to_code(chord: Chord) -> str:
    """Encode a chord into the tuner's chord code, e.g. 'T12+RROO'."""
    thumbs = "".join(str(t.index) for t in sorted(chord.thumbs))
    prefix = f"T{thumbs}+" if thumbs else ""

    by_row: dict[int, list[str]] = {row: [] for row in FINGER_ROWS}
    for key in chord.fingers:
        if key.is_mouse:
            raise ValueError("mouse-row keys cannot be encoded in the custom JSON")
        by_row[key.row].append(key.col)

    code = ""
    for row in FINGER_ROWS:
        cols = by_row[row]
        if len(cols) > 1:
            raise ValueError(
                f"row {row} has {len(cols)} columns; custom JSON supports one per row"
            )
        code += cols[0] if cols else "O"
    return prefix + code


def code_to_chord(code: str) -> Chord:
    """Decode a tuner chord code back into a Chord."""
    s = code
    thumbs: set[ThumbKey] = set()
    if s.startswith("T"):
        plus = s.find("+")
        if plus == -1:
            raise ValueError(f"malformed thumb prefix in chord code: {code!r}")
        for ch in s[1:plus]:
            thumbs.add(ThumbKey(int(ch)))
        s = s[plus + 1 :]
    if len(s) != 4:
        raise ValueError(f"expected 4 finger characters, got {len(s)}: {code!r}")

    fingers: set[FingerKey] = set()
    for i, ch in enumerate(s):
        if ch == "O":
            continue
        if ch not in FINGER_COLS:
            raise ValueError(f"invalid column {ch!r} in chord code: {code!r}")
        fingers.add(FingerKey(i + 1, ch))
    return Chord(fingers=frozenset(fingers), thumbs=frozenset(thumbs))


def _action_key(raw_action: str) -> str:
    """Strip the '[KB]' prefix to get the tuner 'key' value."""
    if raw_action.startswith("[KB]"):
        return raw_action[len("[KB]") :]
    return raw_action


def config_to_custom_json(config: Config) -> tuple[dict, list[str]]:
    """Convert a config to the custom-mapping JSON structure.

    Returns (data, skipped) where skipped describes bindings that could not be
    encoded (system actions, multi-column rows, or mouse-row keys).
    """
    chords: list[dict] = []
    skipped: list[str] = []
    for b in config.bindings:
        if b.action.kind is not ActionKind.KEYBOARD:
            skipped.append(f"{b.raw_action} (system action)")
            continue
        try:
            code = chord_to_code(b.chord)
        except ValueError as exc:
            skipped.append(f"{b.raw_action} ({exc})")
            continue
        chords.append({"chord": code, "key": _action_key(b.raw_action)})
    return {"chords": chords}, skipped


def render_custom_json(config: Config) -> str:
    """Render a config as custom-mapping JSON text."""
    data, _ = config_to_custom_json(config)
    return json.dumps(data, indent=2) + "\n"
