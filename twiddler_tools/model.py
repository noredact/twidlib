"""Canonical data model for Twiddler 4 configuration bindings.

Everything here is grounded in the tuner CSV export (see the repo-root
test_config.csv). Nothing about the Twiddler format is taken from
memory; see AGENTS.md ground-truth rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

FINGER_ROWS = (1, 2, 3, 4)
MOUSE_ROW = 0
FRONT_ROWS = (0, 1, 2, 3, 4)
FINGER_COLS = ("L", "M", "R")
THUMB_KEYS = (0, 1, 2, 3, 4)


class ActionKind(str, Enum):
    KEYBOARD = "keyboard"
    SYSTEM = "system"


@dataclass(frozen=True, order=True)
class ThumbKey:
    """A single thumb key, labelled 0-4 in the CSV 'Thumbs' column."""

    index: int

    def __post_init__(self) -> None:
        if self.index not in THUMB_KEYS:
            raise ValueError(f"thumb key out of range: {self.index}")


@dataclass(frozen=True, order=True)
class FingerKey:
    """A single front-side key: row 0 (mouse) or 1-4 (fingers), col L/M/R."""

    row: int
    col: str

    def __post_init__(self) -> None:
        if self.row not in FRONT_ROWS:
            raise ValueError(f"finger row out of range: {self.row}")
        if self.col not in FINGER_COLS:
            raise ValueError(f"finger column out of range: {self.col!r}")

    @property
    def is_mouse(self) -> bool:
        return self.row == MOUSE_ROW

    def __str__(self) -> str:
        return f"{self.row}{self.col}"


@dataclass(frozen=True)
class Chord:
    """A physical chord: a set of thumb keys plus a set of finger keys."""

    fingers: frozenset[FingerKey] = frozenset()
    thumbs: frozenset[ThumbKey] = frozenset()

    @property
    def chord_id(self) -> str:
        """Canonical identifier, e.g. 'T12:F1L,1M,2R' (T- means no thumbs)."""
        thumbs = ",".join(str(t.index) for t in sorted(self.thumbs))
        fingers = ",".join(str(k) for k in sorted(self.fingers))
        return f"T{thumbs or '-'}:F{fingers or '-'}"


@dataclass(frozen=True)
class TextSegment:
    """Literal text emitted by a keyboard action."""

    text: str


@dataclass(frozen=True)
class ModSegment:
    """A modifier-wrapped segment such as '<RShift>=</RShift>'."""

    modifier: str
    inner: str


@dataclass(frozen=True)
class KeySegment:
    """A named (non-printable) key such as '<F1>' or '<Enter>'."""

    name: str


Segment = TextSegment | ModSegment | KeySegment


@dataclass(frozen=True)
class Action:
    raw: str
    kind: ActionKind
    # Keyboard actions:
    segments: tuple[Segment, ...] = ()
    # System actions:
    subsystem: str = ""
    command: str = ""

    @property
    def typed_text(self) -> str:
        """Literal printable text a keyboard action emits.

        Named keys contribute nothing; plain text and modifier-wrapped inner
        text are concatenated in order. [ASSUMED] Shift semantics are NOT
        applied: '<RShift>=</RShift>' yields '=' and '<RShift>t</RShift>he'
        yields 'the' (matching is case-insensitive in lookup anyway).
        """
        out: list[str] = []
        for seg in self.segments:
            if isinstance(seg, TextSegment):
                out.append(seg.text)
            elif isinstance(seg, ModSegment):
                out.append(seg.inner)
        return "".join(out)


@dataclass(frozen=True)
class Binding:
    """One CSV row: a chord bound to an action, with raw strings preserved."""

    chord: Chord
    action: Action
    raw_thumbs: str
    raw_fingers: str
    raw_action: str


@dataclass
class Config:
    """A whole imported configuration file."""

    bindings: list[Binding]
    source: str = ""


@dataclass
class PendingChord:
    """An inbox item: a chord the user wants to add later."""

    text: str
    status: str = "pending"  # "pending" | "exported"
    chord_id: str | None = None
    created_at: str = ""
    notes: str = ""


_SYS_RE = re.compile(r"^\[SYS\]\[(?P<sub>[^\]]+)\]<(?P<cmd>.+)>$")
_KB_RE = re.compile(r"^\[KB\](?P<inner>.*)$", re.DOTALL)


def parse_action(raw: str) -> Action:
    """Parse a tuner action string into an Action.

    Two families are observed: '[KB]...' (keyboard) and
    '[SYS][Subsystem]<Command>' (system). [VERIFIED]
    """
    m = _SYS_RE.match(raw)
    if m:
        return Action(
            raw=raw,
            kind=ActionKind.SYSTEM,
            subsystem=m.group("sub"),
            command=m.group("cmd"),
        )
    m = _KB_RE.match(raw)
    if m:
        return Action(
            raw=raw,
            kind=ActionKind.KEYBOARD,
            segments=tuple(_parse_kb_inner(m.group("inner"))),
        )
    raise ValueError(f"unrecognised action: {raw!r}")


def _parse_kb_inner(text: str) -> list[Segment]:
    """Split the inside of '[KB]...' into text/mod/key segments."""
    segments: list[Segment] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "<":
            j = text.find(">", i)
            if j == -1:  # unterminated tag: treat the rest as literal text
                segments.append(TextSegment(text[i:]))
                break
            name = text[i + 1 : j]
            closing = f"</{name}>"
            if text.startswith(closing, j + 1):
                end = text.index(closing, j + 1)
                segments.append(ModSegment(name, text[j + 1 : end]))
                i = end + len(closing)
            else:
                segments.append(KeySegment(name))
                i = j + 1
        else:
            k = text.find("<", i)
            if k == -1:
                segments.append(TextSegment(text[i:]))
                break
            segments.append(TextSegment(text[i:k]))
            i = k
    return segments


_FINGER_TOKEN_RE = re.compile(r"^([0-4])([LMR]{1,3})$")


def expand_finger_token(token: str) -> list[FingerKey]:
    """Expand one Fingers-column token like '1LM' or '3MR' into keys."""
    m = _FINGER_TOKEN_RE.match(token)
    if not m:
        raise ValueError(f"invalid finger token: {token!r}")
    row = int(m.group(1))
    return [FingerKey(row, col) for col in m.group(2)]


def parse_finger_tokens(text: str) -> list[FingerKey]:
    """Expand a whole Fingers column value into keys."""
    keys: list[FingerKey] = []
    for token in text.split():
        keys.extend(expand_finger_token(token))
    return keys


def format_chord(chord: Chord) -> str:
    """Render a chord in compact notation, e.g. 'T12 F1LM 2MR'.

    Thumb keys are prefixed 'T', finger keys 'F'. The 'T' part is omitted when
    no thumb keys are pressed.
    """
    parts = []
    if chord.thumbs:
        digits = "".join(str(t.index) for t in sorted(chord.thumbs))
        parts.append(f"T{digits}")
    if chord.fingers:
        by_row: dict[int, list[str]] = {row: [] for row in FRONT_ROWS}
        for key in chord.fingers:
            by_row[key.row].append(key.col)
        tokens = []
        for row in FRONT_ROWS:
            if by_row[row]:
                cols = sorted(by_row[row], key=FINGER_COLS.index)
                tokens.append(f"{row}{''.join(cols)}")
        parts.append("F" + " ".join(tokens))
    return " ".join(parts)


def parse_chord_spec(spec: str) -> Chord:
    """Parse compact chord notation, e.g. 'T12 F1LM 2MR' or 'F2M 3R 4R'.

    The 'T'/'F' prefixes and the thumb token are optional; tokens are space-
    or comma-separated.
    """
    tokens = re.split(r"[\s,]+", spec.strip())
    thumbs: set[ThumbKey] = set()
    fingers: set[FingerKey] = set()
    for token in tokens:
        if not token:
            continue
        if token[0] in "Tt":
            rest = token[1:]
            if rest == "-":
                continue  # explicit "no thumbs" marker (e.g. "T-")
            if not rest or not rest.isdigit():
                raise ValueError(f"invalid thumb token: {token!r}")
            for ch in rest:
                thumbs.add(ThumbKey(int(ch)))
        elif token[0] in "Ff":
            fingers.update(expand_finger_token(token[1:]))
        else:
            fingers.update(expand_finger_token(token))
    return Chord(fingers=frozenset(fingers), thumbs=frozenset(thumbs))


def _space_marker(n: int) -> str:
    return "[sp]" * n


def display_action(raw: str) -> str:
    """Render an action string for display, clarifying bare/trailing spaces.

    Spaces are rendered as '[sp]' (never '_', which is a real character) so a
    chord bound to a space or ending in one is unmistakable.
    """
    if raw.startswith("[KB]"):
        inner = raw[4:]
        if inner.isspace() and inner:
            return "[KB]" + _space_marker(len(inner))
        if inner.endswith(" "):
            n = len(inner) - len(inner.rstrip(" "))
            return "[KB]" + inner.rstrip(" ") + _space_marker(n)
    return raw


def display_text(text: str) -> str:
    """Render output text for display, clarifying all-space and trailing spaces."""
    if text and text.isspace():
        return _space_marker(len(text))
    if text.endswith(" "):
        n = len(text) - len(text.rstrip(" "))
        return text.rstrip(" ") + _space_marker(n)
    return text
