import pytest

from twiddler_tools.model import (
    Chord,
    FingerKey,
    display_action,
    display_text,
    expand_finger_token,
    format_chord,
    parse_chord_spec,
    parse_finger_tokens,
)


def test_expand_finger_token_lm():
    assert set(expand_finger_token("1LM")) == {FingerKey(1, "L"), FingerKey(1, "M")}


def test_expand_finger_token_mr():
    assert set(expand_finger_token("3MR")) == {FingerKey(3, "M"), FingerKey(3, "R")}


def test_expand_finger_token_invalid():
    with pytest.raises(ValueError):
        expand_finger_token("9X")


def test_parse_finger_tokens():
    assert set(parse_finger_tokens("1LM 2LM")) == {
        FingerKey(1, "L"),
        FingerKey(1, "M"),
        FingerKey(2, "L"),
        FingerKey(2, "M"),
    }


def test_parse_chord_spec_or():
    chord = parse_chord_spec("T- 2M 3R 4R")
    assert chord.thumbs == frozenset()
    assert set(chord.fingers) == {
        FingerKey(2, "M"),
        FingerKey(3, "R"),
        FingerKey(4, "R"),
    }


def test_parse_chord_spec_thumbs():
    chord = parse_chord_spec("T12 1LM 2MR")
    assert {t.index for t in chord.thumbs} == {1, 2}
    assert set(chord.fingers) == {
        FingerKey(1, "L"),
        FingerKey(1, "M"),
        FingerKey(2, "M"),
        FingerKey(2, "R"),
    }


def test_parse_chord_spec_commas():
    chord = parse_chord_spec("T12, 3M, 4R")
    assert {t.index for t in chord.thumbs} == {1, 2}
    assert set(chord.fingers) == {FingerKey(3, "M"), FingerKey(4, "R")}


def test_parse_chord_spec_no_thumb_token():
    chord = parse_chord_spec("2M 3R")
    assert chord.thumbs == frozenset()


def test_parse_chord_spec_rejects_lone_t():
    # A bare "t"/"T" is a letter, not a chord, so it must not parse as one.
    with pytest.raises(ValueError):
        parse_chord_spec("t")
    with pytest.raises(ValueError):
        parse_chord_spec("T")


def test_format_chord_round_trip():
    chord = parse_chord_spec("T12 F1LM 2MR")
    assert format_chord(chord) == "T12 F1LM 2MR"


def test_format_chord_no_thumbs():
    chord = parse_chord_spec("F2M 3R 4R")
    assert format_chord(chord) == "F2M 3R 4R"


def test_expand_finger_token_mouse():
    assert set(expand_finger_token("0L")) == {FingerKey(0, "L")}


def test_parse_chord_spec_mouse():
    chord = parse_chord_spec("0L 1M")
    assert set(chord.fingers) == {FingerKey(0, "L"), FingerKey(1, "M")}


def test_format_chord_mouse():
    assert format_chord(parse_chord_spec("0L 1M")) == "F0L 1M"


def test_format_chord_thumbs_only():
    chord = parse_chord_spec("T023")
    assert format_chord(chord) == "T023"


def test_parse_chord_spec_f_prefix():
    chord = parse_chord_spec("F1LM 2MR")
    assert chord.thumbs == frozenset()
    assert set(chord.fingers) == {
        FingerKey(1, "L"),
        FingerKey(1, "M"),
        FingerKey(2, "M"),
        FingerKey(2, "R"),
    }


def test_display_action_space():
    assert display_action("[KB] ") == "[KB][sp]"
    assert display_action("[KB]  ") == "[KB][sp][sp]"
    assert display_action("[KB]or") == "[KB]or"
    assert display_action("[KB]the ") == "[KB]the[sp]"


def test_display_text_space():
    assert display_text(" ") == "[sp]"
    assert display_text("the ") == "the[sp]"
    assert display_text("or") == "or"
