from pathlib import Path

import pytest

from twiddler_tools.csv_io import parse_csv, render_csv
from twiddler_tools.model import ActionKind, FingerKey

SAMPLE = Path(__file__).resolve().parent.parent / "sample_export_csv.csv"


@pytest.fixture(scope="module")
def config():
    return parse_csv(SAMPLE.read_text(encoding="utf-8-sig"), source=str(SAMPLE))


def _find(config, text):
    return [b for b in config.bindings if b.action.typed_text == text]


def test_parses_expected_count(config):
    assert len(config.bindings) == 146


def test_or_chord(config):
    matches = _find(config, "or")
    assert len(matches) == 1
    b = matches[0]
    assert b.raw_thumbs == ""
    assert {k for k in b.chord.fingers} == {
        FingerKey(2, "M"),
        FingerKey(3, "R"),
        FingerKey(4, "R"),
    }


def test_ing_chord(config):
    matches = _find(config, "ing")
    assert len(matches) == 1
    assert {(k.row, k.col) for k in matches[0].chord.fingers} == {(4, "L")}


def test_st_chord(config):
    matches = _find(config, "st")
    assert len(matches) == 1
    assert {(k.row, k.col) for k in matches[0].chord.fingers} == {
        (1, "L"),
        (2, "M"),
        (3, "M"),
    }


def test_lm_expansion(config):
    # "est" -> "1LM 2LM" -> 1L+1M+2L+2M
    matches = _find(config, "est")
    assert len(matches) == 1
    assert {(k.row, k.col) for k in matches[0].chord.fingers} == {
        (1, "L"),
        (1, "M"),
        (2, "L"),
        (2, "M"),
    }


def test_mr_expansion(config):
    # "to" -> "2M 3MR" -> 2M+3M+3R
    matches = _find(config, "to")
    assert len(matches) == 1
    assert {(k.row, k.col) for k in matches[0].chord.fingers} == {
        (2, "M"),
        (3, "M"),
        (3, "R"),
    }


def test_the_has_three_bindings(config):
    # "the" (4M), "<RShift>t</RShift>he" (2+4M and 4+4M) all type "the"/"The"
    assert len(_find(config, "the")) == 3


def test_system_action_parses(config):
    b = [x for x in config.bindings if x.raw_thumbs == "0" and x.raw_fingers == "1R"][0]
    assert b.action.kind is ActionKind.SYSTEM
    assert b.action.subsystem == "KB"
    assert b.action.command == "KB Print System Info"


def test_thumb_expansion(config):
    b = [x for x in config.bindings if x.raw_thumbs == "023"][0]
    assert {t.index for t in b.chord.thumbs} == {0, 2, 3}


def test_round_trip(config):
    text = render_csv(config)
    reparsed = parse_csv(text)
    assert [(b.raw_thumbs, b.raw_fingers, b.raw_action) for b in config.bindings] == [
        (b.raw_thumbs, b.raw_fingers, b.raw_action) for b in reparsed.bindings
    ]
