"""Parse and re-emit the tuner's CSV export.

The CSV is UTF-8 with a BOM, comma-quoted, with the header
'Thumbs,Fingers,Actions'. Raw field values are preserved on each Binding so
parse -> render -> parse is lossless.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .model import (
    Binding,
    Chord,
    Config,
    FingerKey,
    ThumbKey,
    parse_action,
    parse_finger_tokens,
)

HEADER = ["Thumbs", "Fingers", "Actions"]


def parse_csv(text: str, source: str = "") -> Config:
    if text.startswith("\ufeff"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return Config(bindings=[], source=source)
    if rows[0] != HEADER:
        raise ValueError(f"unexpected CSV header: {rows[0]!r}")

    bindings: list[Binding] = []
    for row in rows[1:]:
        if not row or all(cell == "" for cell in row):
            continue
        if len(row) != 3:
            raise ValueError(f"expected 3 columns, got {len(row)}: {row!r}")
        raw_thumbs, raw_fingers, raw_action = row
        bindings.append(
            Binding(
                chord=Chord(
                    fingers=frozenset(_parse_fingers(raw_fingers)),
                    thumbs=frozenset(_parse_thumbs(raw_thumbs)),
                ),
                action=parse_action(raw_action),
                raw_thumbs=raw_thumbs,
                raw_fingers=raw_fingers,
                raw_action=raw_action,
            )
        )
    return Config(bindings=bindings, source=source)


def render_csv(config: Config) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(HEADER)
    for b in config.bindings:
        writer.writerow([b.raw_thumbs, b.raw_fingers, b.raw_action])
    return out.getvalue()


def load_csv(path: str | Path) -> Config:
    p = Path(path)
    return parse_csv(p.read_text(encoding="utf-8-sig"), source=str(p))


def _parse_thumbs(raw: str) -> list[ThumbKey]:
    if any(not ch.isdigit() for ch in raw):
        raise ValueError(f"unexpected thumb token: {raw!r}")
    return [ThumbKey(int(ch)) for ch in raw]


def _parse_fingers(raw: str) -> list[FingerKey]:
    return parse_finger_tokens(raw)
