"""Look up bindings by the text they type, or by chord."""

from __future__ import annotations

from .model import ActionKind, Binding, Chord, Config, FingerKey, KeySegment


def find_by_text(config: Config, query: str) -> list[Binding]:
    """Return bindings whose keyboard output matches the query.

    Matching is case-insensitive. Exact output-text matches are returned when
    any exist; otherwise substring matches are returned.
    """
    q = query.strip().lower()
    if not q:
        return []
    keyboard = [b for b in config.bindings if b.action.kind is ActionKind.KEYBOARD]
    exact = [b for b in keyboard if b.action.typed_text.lower() == q]
    if exact:
        return exact
    return [b for b in keyboard if q in b.action.typed_text.lower()]


def find_by_chord(config: Config, chord: Chord) -> list[Binding]:
    """Return every binding on a given physical chord (reverse lookup)."""
    return [b for b in config.bindings if b.chord == chord]


def find_by_segment_names(config: Config, names: set[str] | frozenset[str]) -> list[Binding]:
    """Return keyboard bindings that emit a named key in `names`.

    Matches any '[KB]<Name>' standalone key tag such as '<CapsLock>' or
    '<NumLock>', plus '<Return>' aliases.
    """
    result = []
    for b in config.bindings:
        if b.action.kind is ActionKind.KEYBOARD:
            for seg in b.action.segments:
                if isinstance(seg, KeySegment) and seg.name in names:
                    result.append(b)
                    break
    return result


def system_actions(config: Config) -> list[tuple[str, str]]:
    """Unique (subsystem, command) pairs across all system bindings."""
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for b in config.bindings:
        if b.action.kind is ActionKind.SYSTEM:
            key = (b.action.subsystem, b.action.command)
            if key not in seen:
                seen.add(key)
                result.append(key)
    return result


def find_by_system_action(
    config: Config, subsystem: str, command: str
) -> list[Binding]:
    """Return every binding for a given system action."""
    return [
        b
        for b in config.bindings
        if b.action.kind is ActionKind.SYSTEM
        and b.action.subsystem == subsystem
        and b.action.command == command
    ]


def find_by_finger_key(config: Config, row: int, col: str) -> list[Binding]:
    """Return bindings whose chord includes a specific front-side key."""
    target = FingerKey(row, col)
    return [b for b in config.bindings if target in b.chord.fingers]
