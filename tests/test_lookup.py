from pathlib import Path

import pytest

from twiddler_tools.csv_io import parse_csv
from twiddler_tools.lookup import find_by_chord, find_by_finger_key, find_by_text
from twiddler_tools.model import (
    Binding,
    Chord,
    Config,
    FingerKey,
    parse_action,
    parse_chord_spec,
)

SAMPLE = Path(__file__).resolve().parent.parent / "sample_export_csv.csv"


@pytest.fixture(scope="module")
def config():
    return parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))


def test_exact_match_case_insensitive(config):
    res = find_by_text(config, "OR")
    assert len(res) == 1
    assert res[0].action.typed_text == "or"


def test_multiple_matches(config):
    res = find_by_text(config, "the")
    assert len(res) == 3


def test_exact_prefers_over_substring(config):
    # "ion" exists exactly, so substring matches (e.g. "tion") must not appear
    res = find_by_text(config, "ion")
    assert res and all(b.action.typed_text == "ion" for b in res)


def test_no_match(config):
    assert find_by_text(config, "zz") == []


def test_whitespace_query_is_empty(config):
    assert find_by_text(config, "   ") == []


def test_find_by_chord(config):
    chord = parse_chord_spec("F2M 3R 4R")  # "or"
    res = find_by_chord(config, chord)
    assert len(res) == 1
    assert res[0].action.typed_text == "or"


def test_find_by_chord_no_match(config):
    chord = parse_chord_spec("T12 F1LM 2MR")
    assert find_by_chord(config, chord) == []


def test_find_by_segment_names_capslock(config):
    from twiddler_tools.lookup import find_by_segment_names

    res = find_by_segment_names(config, {"CapsLock"})
    assert len(res) == 1
    assert res[0].raw_action == "[KB]<CapsLock>"


def test_find_by_segment_names_enter_alias(config):
    from twiddler_tools.lookup import find_by_segment_names

    res = find_by_segment_names(config, {"Return", "Enter"})
    assert len(res) == 2
    assert all("Enter" in b.raw_action for b in res)


def test_system_actions(config):
    from twiddler_tools.lookup import system_actions

    actions = system_actions(config)
    assert ("Sleep", "Sleep Sleep Now") in actions
    assert ("KB", "KB Print System Info") in actions


def test_find_by_system_action(config):
    from twiddler_tools.lookup import find_by_system_action

    res = find_by_system_action(config, "Sleep", "Sleep Sleep Now")
    assert len(res) == 1
    assert res[0].raw_thumbs == "023"


def test_find_by_finger_key():
    cfg = Config(
        bindings=[
            Binding(
                chord=Chord(fingers=frozenset({FingerKey(0, "L")})),
                action=parse_action("[KB]click"),
                raw_thumbs="",
                raw_fingers="0L",
                raw_action="[KB]click",
            )
        ]
    )
    assert len(find_by_finger_key(cfg, 0, "L")) == 1
    assert find_by_finger_key(cfg, 0, "R") == []
