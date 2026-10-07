"""Render a chord as layout data for the keymap widget.

The GUI widget owns the actual drawing; this module just reduces a Chord to
the set of physical keys that must be highlighted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FINGER_COLS, FINGER_ROWS, MOUSE_ROW, THUMB_KEYS, Chord


@dataclass(frozen=True)
class ActiveKeys:
    thumbs: frozenset[int]
    fingers: frozenset[tuple[int, str]]


def active_keys(chord: Chord) -> ActiveKeys:
    """Which thumb and finger keys a chord presses."""
    return ActiveKeys(
        thumbs=frozenset(t.index for t in chord.thumbs),
        fingers=frozenset((k.row, k.col) for k in chord.fingers),
    )


def layout() -> dict:
    """Static description of the physical keymap used by the widget."""
    return {
        "mouse_row": MOUSE_ROW,
        "rows": FINGER_ROWS,
        "cols": FINGER_COLS,
        "thumbs": THUMB_KEYS,
    }
