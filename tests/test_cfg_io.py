"""Tests for the v7 .cfg reader/writer, grounded in the paired samples."""

import csv
from pathlib import Path

import pytest

from twiddler_tools import cfg_io
from twiddler_tools.model import Chord, FingerKey, ThumbKey

SAMPLES = Path(__file__).parent.parent / "sample_config_files"
CUSTOM_CFG = SAMPLES / "test_config1.cfg"
CUSTOM_CSV = SAMPLES / "test_config1.csv"
DEFAULT_CFG = SAMPLES / "test_config2.cfg"


def _chord(**kwargs):
    return Chord(**kwargs)


def _f(row, col):
    return FingerKey(row, col)


def _t(index):
    return ThumbKey(index)


def test_combo_round_trip():
    chords = [
        Chord(fingers=frozenset({_f(4, "L")})),                       # "ing"
        Chord(fingers=frozenset({_f(4, "M")})),                       # "the"
        Chord(fingers=frozenset({_f(1, "M"), _f(1, "L"), _f(2, "M"), _f(2, "L")})),
        Chord(fingers=frozenset({_f(1, "R")}), thumbs=frozenset({_t(1)})),
        Chord(fingers=frozenset({_f(0, "M")})),                       # mouse middle
        Chord(fingers=frozenset({_f(0, "L")})),                       # mouse left
        Chord(fingers=frozenset({_f(0, "R")})),                       # mouse right
        Chord(fingers=frozenset({_f(3, "R")}), thumbs=frozenset({_t(0)})),
        Chord(fingers=frozenset({_f(4, "R")}), thumbs=frozenset({_t(1), _t(2)})),
    ]
    for ch in chords:
        combo = cfg_io.chord_to_combo(ch)
        assert cfg_io.combo_to_chord(combo) == ch, ch.chord_id


def test_known_combos():
    # Verified against the reference bitfield layout.
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(4, "L")}))) == 0x8000  # ing
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(4, "M")}))) == 0x4000  # the
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(4, "R")}))) == 0x2000  # and
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(1, "R")}))) == 0x0002
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset(), thumbs=frozenset({_t(1)}))) == 0x0001
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset(), thumbs=frozenset({_t(0)}))) == 0x00080000
    assert cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(0, "M")}))) == 0x00020000


def test_parse_custom_header():
    cfg = cfg_io.parse_cfg(CUSTOM_CFG.read_bytes())
    assert cfg.version == 7
    assert cfg.num_chords == 145
    assert len(cfg.records) == 145
    # "ing" is bound to F4L (combo 0x8000)
    assert any(r.combo == 0x8000 and r.command_type == cfg_io.OP_MACRO for r in cfg.records)


def test_custom_macros_round_trip():
    data = CUSTOM_CFG.read_bytes()
    macros = cfg_io.macros_in(data)
    # Known macros from the paired CSV.
    assert macros[0x8000] == "ing"
    assert macros[0x4000] == "the"
    assert macros[0x2000] == "and"
    # Every decoded macro re-encodes to its own bytes.
    cfg = cfg_io.parse_cfg(data)
    for r in cfg.records:
        if r.command_type == cfg_io.OP_MACRO:
            text = macros[r.combo]
            assert cfg_io.macro_decode(cfg_io.macro_encode(text), 0) == text


def test_default_macros_round_trip():
    data = DEFAULT_CFG.read_bytes()
    cfg = cfg_io.parse_cfg(data)
    assert cfg.version == 7
    assert cfg.num_chords == 111
    for r in cfg.records:
        if r.command_type == cfg_io.OP_MACRO:
            text = cfg_io.macro_decode(cfg.table, r.offset)
            assert cfg_io.macro_decode(cfg_io.macro_encode(text), 0) == text


def test_add_macro():
    base = CUSTOM_CFG.read_bytes()
    new_chord = Chord(fingers=frozenset({_f(2, "R"), _f(2, "M")}))
    out = cfg_io.add_macros(base, [(new_chord, "zz")])

    new_cfg = cfg_io.parse_cfg(out)
    assert new_cfg.num_chords == 146
    # File length updated in bytes 2-3.
    import struct
    assert struct.unpack_from("<H", out, 2)[0] == len(out)

    macros = cfg_io.macros_in(out)
    combo = cfg_io.chord_to_combo(new_chord)
    assert macros[combo] == "zz"
    # Original macros intact.
    assert macros[0x8000] == "ing"
    assert macros[0x4000] == "the"


def test_add_macro_uppercase_and_shifted():
    base = DEFAULT_CFG.read_bytes()
    out = cfg_io.add_macros(
        base,
        [
            (Chord(fingers=frozenset({_f(1, "R"), _f(1, "M")})), "Ab"),
            (Chord(fingers=frozenset({_f(2, "R"), _f(2, "M")})), "hi!"),
        ],
    )
    macros = cfg_io.macros_in(out)
    assert macros[cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(1, "R"), _f(1, "M")})))] == "Ab"
    assert macros[cfg_io.chord_to_combo(Chord(fingers=frozenset({_f(2, "R"), _f(2, "M")})))] == "hi!"


def test_add_macro_duplicate_raises():
    base = CUSTOM_CFG.read_bytes()
    with pytest.raises(ValueError):
        cfg_io.add_macros(base, [(Chord(fingers=frozenset({_f(4, "L")})), "dup")])


def test_add_macro_empty_chord_raises():
    base = CUSTOM_CFG.read_bytes()
    with pytest.raises(ValueError):
        cfg_io.add_macros(base, [(Chord(), "nothing")])


def test_replace_macros():
    base = CUSTOM_CFG.read_bytes()
    # "ing" is F4L (combo 0x8000) in the custom cfg; reassign it to "zz".
    replacements = [(Chord(fingers=frozenset({_f(4, "L")})), "zz")]
    out = cfg_io.replace_macros(base, replacements)

    assert cfg_io.parse_cfg(out).num_chords == cfg_io.parse_cfg(base).num_chords
    macros = cfg_io.macros_in(out)
    assert macros[0x8000] == "zz"
    assert macros[0x4000] == "the"  # untouched
    import struct
    assert struct.unpack_from("<H", out, 2)[0] == len(out)


def test_replace_macros_unknown_chord_raises():
    base = CUSTOM_CFG.read_bytes()
    # F2R+F2M is not bound in the custom cfg.
    chord = Chord(fingers=frozenset({_f(2, "R"), _f(2, "M")}))
    with pytest.raises(ValueError):
        cfg_io.replace_macros(base, [(chord, "x")])


def test_cfg_to_config_matches_csv():
    raw = CUSTOM_CFG.read_bytes()
    config = cfg_io.cfg_to_config(cfg_io.parse_cfg(raw))
    rows = list(csv.reader(CUSTOM_CSV.open(encoding="utf-8-sig")))
    csv_map = {(r[0], r[1]): r[2] for r in rows[1:]}
    assert len(config.bindings) == len(csv_map) == 145
    for b in config.bindings:
        assert csv_map.get((b.raw_thumbs, b.raw_fingers)) == b.raw_action


def test_system_action_mapping():
    # Verified against the paired .cfg records + CSV (the Rust reference
    # comments had commands 2 and 12 swapped).
    assert cfg_io.SYSTEM_ACTIONS[2] == "[SYS][KB]<KB Print System Info>"
    assert cfg_io.SYSTEM_ACTIONS[12] == "[SYS][LED]<LED Keyboard LEDs>"


def test_settings_round_trip(tmp_path, monkeypatch):
    from twiddler_tools import settings

    sample = Path(__file__).parent.parent / "test_config.csv"
    monkeypatch.setattr(settings, "state_path", lambda: tmp_path / "state.json")

    settings.save_last_config(str(sample), "csv")
    config, base = settings.load_last_config()
    assert base is None
    assert len(config.bindings) > 0

    cfg_file = tmp_path / "x.cfg"
    cfg_file.write_bytes(CUSTOM_CFG.read_bytes())
    settings.save_last_config(str(cfg_file), "cfg")
    config, base = settings.load_last_config()
    assert base is not None
    assert len(config.bindings) == 145


def test_settings_missing_file_falls_back_empty(tmp_path, monkeypatch):
    from twiddler_tools import settings

    monkeypatch.setattr(settings, "state_path", lambda: tmp_path / "state.json")
    settings.save_last_config(str(tmp_path / "gone.csv"), "csv")
    config, base = settings.load_last_config()
    assert len(config.bindings) == 0
    assert base is None


def test_config_to_cfg_round_trip():
    for path in (CUSTOM_CFG, DEFAULT_CFG):
        raw = path.read_bytes()
        config = cfg_io.cfg_to_config(cfg_io.parse_cfg(raw))
        rebuilt = cfg_io.config_to_cfg(config, raw)
        config2 = cfg_io.cfg_to_config(cfg_io.parse_cfg(rebuilt))
        a = [(b.raw_thumbs, b.raw_fingers, b.raw_action) for b in config.bindings]
        b = [(b.raw_thumbs, b.raw_fingers, b.raw_action) for b in config2.bindings]
        assert a == b
        # Settings are preserved from the base header.
        base = cfg_io.parse_cfg(raw)
        out = cfg_io.parse_cfg(rebuilt)
        assert out.flags == base.flags
        assert out.idle_time == base.idle_time
        assert out.mouse_sensitivity == base.mouse_sensitivity
        assert out.key_repeat_delay == base.key_repeat_delay


def test_action_to_record_shifted_single_key():
    # '<RShift>=</RShift>' is stored as one keyboard record: RShift + the '=' key.
    ctype, d0, d1, macro = cfg_io.action_to_record("[KB]<RShift>=</RShift>")
    assert ctype == cfg_io.OP_KEYBOARD
    assert (d0, d1) == (0x20, 0x2E)
    assert macro is None


def test_action_to_record_macro():
    ctype, d0, d1, macro = cfg_io.action_to_record("[KB]<RShift>t</RShift>he")
    assert ctype == cfg_io.OP_MACRO
    assert macro == [(0x20, 0x17), (0x00, 0x0B), (0x00, 0x08)]  # RShift+t, h, e
    assert (d0, d1) == (0, 0)  # offset is assigned later


def test_action_to_record_system_and_mouse():
    assert cfg_io.action_to_record("[SYS][Sleep]<Sleep Sleep Now>")[:3] == (cfg_io.OP_SYSTEM, 1, 0)
    assert cfg_io.action_to_record("[SYS][Mouse]<Mouse Left Click>")[:3] == (cfg_io.OP_MOUSE, 1, 0)


def test_config_to_cfg_from_csv():
    from twiddler_tools.csv_io import load_csv

    csv_config = load_csv(str(CUSTOM_CSV))
    out = cfg_io.config_to_cfg(csv_config, CUSTOM_CFG.read_bytes())
    back = cfg_io.cfg_to_config(cfg_io.parse_cfg(out))
    csv_rows = {(b.raw_thumbs, b.raw_fingers, b.raw_action) for b in csv_config.bindings}
    back_rows = {(b.raw_thumbs, b.raw_fingers, b.raw_action) for b in back.bindings}
    assert csv_rows == back_rows


def test_config_to_cfg_rejects_unknown_action():
    from twiddler_tools.model import Binding, Config

    bad = Config(
        bindings=[
            Binding(
                chord=Chord(fingers=frozenset({_f(1, "L")})),
                action=cfg_io.parse_action("[KB]a"),
                raw_thumbs="",
                raw_fingers="1L",
                raw_action="[KB]<NotARealKey>",
            )
        ],
        source="",
    )
    with pytest.raises(ValueError):
        cfg_io.config_to_cfg(bad, CUSTOM_CFG.read_bytes())
