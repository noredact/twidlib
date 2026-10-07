import json
from pathlib import Path

import pytest

from twiddler_tools.json_io import (
    chord_to_code,
    code_to_chord,
    config_to_custom_json,
    render_custom_json,
)
from twiddler_tools.model import (
    Binding,
    Chord,
    Config,
    FingerKey,
    ThumbKey,
    parse_action,
)

MIRROR = (
    Path(__file__).resolve().parent.parent
    / "test_json.json"
)


def _chord(fingers=(), thumbs=()):
    return Chord(
        fingers=frozenset(FingerKey(r, c) for r, c in fingers),
        thumbs=frozenset(ThumbKey(t) for t in thumbs),
    )


def test_chord_to_code_basic():
    assert chord_to_code(_chord(fingers=[(1, "R"), (2, "R")])) == "RROO"
    assert chord_to_code(_chord(fingers=[(1, "M"), (2, "L"), (3, "M"), (4, "L")])) == "MLML"
    assert chord_to_code(_chord(fingers=[(4, "L")])) == "OOOL"


def test_chord_to_code_thumbs():
    assert chord_to_code(_chord(fingers=[(1, "R")], thumbs=[1])) == "T1+ROOO"
    assert chord_to_code(_chord(fingers=[(1, "R")], thumbs=[1, 2])) == "T12+ROOO"


def test_chord_to_code_rejects_multi_column_row():
    with pytest.raises(ValueError):
        chord_to_code(_chord(fingers=[(1, "L"), (1, "M")]))


def test_chord_to_code_rejects_mouse():
    with pytest.raises(ValueError):
        chord_to_code(_chord(fingers=[(0, "L")]))


def test_code_to_chord_round_trip():
    assert code_to_chord("RROO") == _chord(fingers=[(1, "R"), (2, "R")])
    assert code_to_chord("T12+ROOO") == _chord(fingers=[(1, "R")], thumbs=[1, 2])
    assert code_to_chord("OOOL") == _chord(fingers=[(4, "L")])


def test_mirror_json_round_trip():
    data = json.loads(MIRROR.read_text(encoding="utf-8"))
    assert len(data["chords"]) > 100
    for entry in data["chords"]:
        chord = code_to_chord(entry["chord"])
        assert chord_to_code(chord) == entry["chord"]


def test_config_to_custom_json_key_stripping():
    cfg = Config(
        bindings=[
            Binding(
                chord=_chord(fingers=[(1, "R")]),
                action=parse_action("[KB]<F1>"),
                raw_thumbs="",
                raw_fingers="1R",
                raw_action="[KB]<F1>",
            ),
            Binding(
                chord=_chord(fingers=[(2, "M")]),
                action=parse_action("[KB]; "),
                raw_thumbs="",
                raw_fingers="2M",
                raw_action="[KB]; ",
            ),
        ]
    )
    data, skipped = config_to_custom_json(cfg)
    assert data["chords"] == [
        {"chord": "ROOO", "key": "<F1>"},
        {"chord": "OMOO", "key": "; "},
    ]
    assert skipped == []


def test_config_to_custom_json_skips():
    cfg = Config(
        bindings=[
            Binding(
                chord=_chord(fingers=[(1, "L"), (1, "M")]),
                action=parse_action("[KB]est"),
                raw_thumbs="",
                raw_fingers="1LM",
                raw_action="[KB]est",
            ),
            Binding(
                chord=_chord(thumbs=[0, 2, 3]),
                action=parse_action("[SYS][Sleep]<Sleep Sleep Now>"),
                raw_thumbs="023",
                raw_fingers="",
                raw_action="[SYS][Sleep]<Sleep Sleep Now>",
            ),
        ]
    )
    data, skipped = config_to_custom_json(cfg)
    assert data["chords"] == []
    assert len(skipped) == 2


def test_render_custom_json():
    cfg = Config(bindings=[])
    assert render_custom_json(cfg) == '{\n  "chords": []\n}\n'
