"""Twiddler v7 `.cfg` binary config — parse and write.

Format facts are implemented from the v7 format research and exercised with
synthetic fixtures in the test suite:

Header (0x80 bytes):
  00-03  4 bytes: tag/checksum + file length. Bytes 2-3 hold the file length
         (u16 LE); bytes 0-1 are a tag the tuner/firmware writes (algorithm
         unknown). The writer preserves bytes 0-1 and updates bytes 2-3.
  04     version (7)
  05-06  config flags (u16 LE bitfield): repeat_delay_enable, ?bluetooth,
         haptic, direct, sticky_num/alt/ctrl/shift, left_mouse_pos, ...
  07     reserved (0)
  08-09  number of chords (u16 LE) — includes the trailing system chords
  0A-0B  idle time (seconds, u16 LE)
  0C     mouse sensitivity
  0D     key repeat delay
  0E-43  zeros
  44-7F  fixed lookup table (60 bytes, identical across files)
  80..   chord records (8 bytes each)

Chord record (8 bytes):
  <button bits, 3 bytes><pad 0><command type u8><data 2 bytes><pad 0>

  Button bits (LSB-first, 3 bytes = 20 used bits):
    bit 0=T1  1=F1R  2=F1M  3=F1L
    bit 4=T2  5=F2R  6=F2M  7=F2L
    bit 8=T3  9=F3R 10=F3M 11=F3L
    bit 12=T4 13=F4R 14=F4M 15=F4L
    bit 16=F0R 17=F0M 18=F0L 19=T0
    bits 20-23 unused

  Command types:
    1 = System   data = [command id][0]
    2 = Keyboard data = [HID modifier][HID keycode]
    3 = Mouse    data = [button bitfield][0]   (1=left, 2=right, 4=middle)
    5 = Delay    data = [duration u16]  (milliseconds / 10)
    7 = Macro    data = [offset u16] into the macro table

Macro table (immediately after the records): each macro is a run of 4-byte
commands, each `<type u8><data 2 bytes><pad 0>`; for keyboard: type 2,
modifier (0x20 = right shift) + keycode. Terminated by 4 zero bytes.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from .model import Binding, Chord, Config, FingerKey, ThumbKey, parse_action

HEADER_SIZE = 0x80
RECORD_SIZE = 8
OP_NONE = 0x00
OP_SYSTEM = 0x01
OP_KEYBOARD = 0x02
OP_MOUSE = 0x03
OP_DELAY = 0x05
OP_MACRO = 0x07

# HID keycodes for printable keys (unshifted layout).
_CHAR_TO_KEY = {
    "a": 4, "b": 5, "c": 6, "d": 7, "e": 8, "f": 9, "g": 10, "h": 11,
    "i": 12, "j": 13, "k": 14, "l": 15, "m": 16, "n": 17, "o": 18, "p": 19,
    "q": 20, "r": 21, "s": 22, "t": 23, "u": 24, "v": 25, "w": 26, "x": 27,
    "y": 28, "z": 29,
    "1": 30, "2": 31, "3": 32, "4": 33, "5": 34, "6": 35, "7": 36, "8": 37,
    "9": 38, "0": 39, " ": 44,
    "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49, ";": 51, "'": 52, "`": 53,
    ",": 54, ".": 55, "/": 56,
}
_SHIFTED_CHARS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "~": "`", "<": ",", ">": ".", "?": "/",
}
_KEY_TO_CHAR = {v: k for k, v in _CHAR_TO_KEY.items()}
_SHIFTED_TO_BASE = {v: k for k, v in _SHIFTED_CHARS.items()}

# Bytes 0x44..0x7F of every v7 config (fixed lookup table).
FIXED_TABLE = bytes.fromhex(
    "0300000001000000020000000A0B090900000000000000000000000000"
    "0102030405060708090A0C0D0F111416181A1D808080808080808080808080"
)


def char_to_op_key(ch: str) -> tuple[int, int]:
    """Map a character to (opcode, HID keycode) for a macro entry."""
    if ch in _CHAR_TO_KEY:
        return 0x0002, _CHAR_TO_KEY[ch]
    if ch in _SHIFTED_CHARS:
        return 0x2002, _CHAR_TO_KEY[_SHIFTED_CHARS[ch]]
    if ch.isalpha():  # uppercase letters: right-shift + base keycode
        return 0x2002, _CHAR_TO_KEY[ch.lower()]
    raise ValueError(f"cannot encode character in macro: {ch!r}")


def macro_encode(text: str) -> bytes:
    """Encode a macro string as a list of keyboard commands + terminator."""
    out = bytearray()
    for ch in text:
        op, key = char_to_op_key(ch)
        out += struct.pack("<HH", op, key)
    out += b"\x00\x00\x00\x00"  # CommandType::None terminator
    return bytes(out)


def macro_decode(table: bytes, offset: int) -> str:
    """Decode a macro from the table at `offset` into its tuner action text."""
    commands: list[tuple[int, int, int]] = []
    i = offset
    while i + 4 <= len(table):
        op, data0, data1 = table[i], table[i + 1], table[i + 2]
        if op == 0:
            break
        commands.append((op, data0, data1))
        i += 4
    if (
        len(commands) == 3
        and commands[0][0] == OP_MOUSE
        and commands[1][0] == OP_DELAY
        and commands[2] == (OP_MOUSE, 0, 0)
    ):
        button = {1: "Left", 2: "Right", 4: "Middle"}.get(commands[0][1])
        if button is not None and commands[0][2] == 0:
            delay = (commands[1][1] | (commands[1][2] << 8)) * 10
            return f"[MS]Down: {button}\n[DLY]{delay}ms[MS]Release"

    out: list[str] = []
    for op, data0, data1 in commands:
        if op == OP_KEYBOARD:
            key = data1
            base = _KEY_TO_CHAR.get(key)
            mod = data0
            if mod == 0:
                out.append(base if base is not None else "?")
            elif mod == _MOD_BITS["RShift"]:
                if base is None:
                    out.append("?")
                elif base.isalpha():
                    out.append(base.upper())
                else:
                    out.append(_SHIFTED_TO_BASE.get(base, "?"))
            else:
                out.append("?")
        else:
            out.append("?")
    return "".join(out)


def chord_to_combo(chord: Chord) -> int:
    """Pack a Chord into the v7 button bitmask."""
    c = 0
    for t in chord.thumbs:
        c |= 1 << 19 if t.index == 0 else 1 << (4 * (t.index - 1))
    for k in chord.fingers:
        if k.row == 0:
            c |= 1 << (16 + {"R": 0, "M": 1, "L": 2}[k.col])
        else:
            c |= 1 << (4 * (k.row - 1) + 1 + {"R": 0, "M": 1, "L": 2}[k.col])
    return c


def combo_to_chord(combo: int) -> Chord:
    """Unpack the v7 button bitmask into a Chord."""
    thumbs: set[ThumbKey] = set()
    fingers: set[FingerKey] = set()
    for r in range(1, 5):
        base = 4 * (r - 1)
        if combo & (1 << base):
            thumbs.add(ThumbKey(r))
        if combo & (1 << (base + 1)):
            fingers.add(FingerKey(r, "R"))
        if combo & (1 << (base + 2)):
            fingers.add(FingerKey(r, "M"))
        if combo & (1 << (base + 3)):
            fingers.add(FingerKey(r, "L"))
    if combo & (1 << 19):
        thumbs.add(ThumbKey(0))
    if combo & (1 << 16):
        fingers.add(FingerKey(0, "R"))
    if combo & (1 << 17):
        fingers.add(FingerKey(0, "M"))
    if combo & (1 << 18):
        fingers.add(FingerKey(0, "L"))
    return Chord(fingers=frozenset(fingers), thumbs=frozenset(thumbs))


@dataclass
class Record:
    combo: int
    command_type: int
    data0: int
    data1: int

    @property
    def offset(self) -> int:
        """For macro records: offset into the macro table."""
        return self.data0 | (self.data1 << 8)


@dataclass
class Cfg:
    raw: bytes
    version: int = 0
    flags: int = 0
    num_chords: int = 0
    idle_time: int = 0
    mouse_sensitivity: int = 0
    key_repeat_delay: int = 0
    records: list[Record] = field(default_factory=list)
    table: bytes = b""


def parse_cfg(data: bytes) -> Cfg:
    if len(data) < HEADER_SIZE:
        raise ValueError("file too small for a .cfg header")
    cfg = Cfg(raw=data)
    cfg.version = data[4]
    cfg.flags = struct.unpack_from("<H", data, 5)[0]
    cfg.num_chords = struct.unpack_from("<H", data, 8)[0]
    cfg.idle_time = struct.unpack_from("<H", data, 0x0A)[0]
    cfg.mouse_sensitivity = data[0x0C]
    cfg.key_repeat_delay = data[0x0D]

    off = HEADER_SIZE
    for _ in range(cfg.num_chords):
        combo = struct.unpack_from("<I", data, off)[0]
        command_type = data[off + 4]
        cfg.records.append(
            Record(
                combo=combo,
                command_type=command_type,
                data0=data[off + 5],
                data1=data[off + 6],
            )
        )
        off += RECORD_SIZE
    cfg.table = data[off:]
    return cfg


def macros_in(data: bytes) -> dict[int, str]:
    """Return {combo: text} for every macro record in a .cfg."""
    cfg = parse_cfg(data)
    return {
        r.combo: macro_decode(cfg.table, r.offset)
        for r in cfg.records
        if r.command_type == OP_MACRO
    }


# Named (non-printable) HID keys, using the tuner's tag names.
_KEYCODE_NAME = {
    0x28: "Enter", 0x29: "Escape", 0x2A: "Backspace", 0x2B: "Tab",
    0x39: "CapsLock",
    **{0x3A + i: f"F{i + 1}" for i in range(12)},
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp", 0x4C: "Delete",
    0x4D: "End", 0x4E: "PageDown",
    0x4F: "RightArrow", 0x50: "LeftArrow", 0x51: "DownArrow", 0x52: "UpArrow",
    0x53: "NumLock",
    0x54: "KP/", 0x55: "KP*", 0x56: "KP-", 0x57: "KP+", 0x58: "KPEnter",
    0x59: "KP1", 0x5A: "KP2", 0x5B: "KP3", 0x5C: "KP4", 0x5D: "KP5",
    0x5E: "KP6", 0x5F: "KP7", 0x60: "KP8", 0x61: "KP9", 0x62: "KP0",
    0x63: "KP.",
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
}

_MOD_NAMES = {
    0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI",
    0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RGUI",
}

# System command id -> tuner CSV action string (verified against the paired
# .cfg records + CSV: command 2 = KB print, command 12 = LED keyboard LEDs).
SYSTEM_ACTIONS = {
    1: "[SYS][Sleep]<Sleep Sleep Now>",
    2: "[SYS][KB]<KB Print System Info>",
    4: "[SYS][Config]<Config Show/Cycle>",
    5: "[SYS][BT]<BT Show/Cycle>",
    6: "[SYS][BT]<BT Clear>",
    10: "[SYS][LED]<LED Battery Level>",
    11: "[SYS][Nav]<Nav Show/Cycle>",
    12: "[SYS][LED]<LED Keyboard LEDs>",
}


def _command_inner(mod: int, key: int) -> str:
    """Render one keyboard command's inner text, tuner-CSV style."""
    base = f"<{_KEYCODE_NAME[key]}>" if key in _KEYCODE_NAME else _KEY_TO_CHAR.get(key)
    if base is None:
        base = f"<?{key:02x}>"
    if mod == 0:
        return base
    names = [_MOD_NAMES[bit] for bit in _MOD_NAMES if mod & bit]
    for name in reversed(names):
        base = f"<{name}>{base}</{name}>"
    return base


def _macro_inner(table: bytes, offset: int) -> str:
    commands: list[tuple[int, int, int]] = []
    i = offset
    while i + 4 <= len(table):
        op, data0, data1 = table[i], table[i + 1], table[i + 2]
        if op == 0:
            break
        commands.append((op, data0, data1))
        i += 4
    if (
        len(commands) == 3
        and commands[0][0] == OP_MOUSE
        and commands[1][0] == OP_DELAY
        and commands[2] == (OP_MOUSE, 0, 0)
    ):
        button = {1: "Left", 2: "Right", 4: "Middle"}.get(commands[0][1])
        if button is not None and commands[0][2] == 0:
            delay = (commands[1][1] | (commands[1][2] << 8)) * 10
            return f"[MS]Down: {button}\n[DLY]{delay}ms[MS]Release"
    return "".join(
        _command_inner(data0, data1) if op == OP_KEYBOARD else f"<op{op}>"
        for op, data0, data1 in commands
    )


def _finger_tokens(chord: Chord) -> str:
    """Render the chord's finger keys in CSV Fingers-column style."""
    by_row: dict[int, list[str]] = {}
    for k in chord.fingers:
        by_row.setdefault(k.row, []).append(k.col)
    tokens = []
    for row in sorted(by_row):
        cols = sorted(by_row[row], key="LMR".index)
        tokens.append(f"{row}{''.join(cols)}")
    return " ".join(tokens)


def _record_action(cfg: Cfg, r: Record) -> str:
    if r.command_type == OP_KEYBOARD:
        return "[KB]" + _command_inner(r.data0, r.data1)
    if r.command_type == OP_MACRO:
        inner = _macro_inner(cfg.table, r.offset)
        return inner if inner.startswith("[MS]") else "[KB]" + inner
    if r.command_type == OP_SYSTEM:
        return SYSTEM_ACTIONS.get(r.data0, f"[SYS][?]<Command {r.data0}>")
    if r.command_type == OP_MOUSE:
        name = {1: "Left", 2: "Right", 4: "Middle"}.get(r.data0, f"{r.data0:02x}")
        return f"[SYS][Mouse]<Mouse {name} Click>"
    if r.command_type == OP_DELAY:
        return f"[SYS][Delay]<{r.data0 | (r.data1 << 8)}0ms>"
    return f"[SYS][?]<op {r.command_type}>"


def cfg_to_config(cfg: Cfg, source: str = "") -> Config:
    """Convert a parsed .cfg into the model Config (for lookup/inbox)."""
    bindings = []
    for r in cfg.records:
        chord = combo_to_chord(r.combo)
        raw_action = _record_action(cfg, r)
        action = parse_action(raw_action)
        raw_thumbs = "".join(str(t.index) for t in sorted(chord.thumbs))
        bindings.append(
            Binding(
                chord=chord,
                action=action,
                raw_thumbs=raw_thumbs,
                raw_fingers=_finger_tokens(chord),
                raw_action=raw_action,
            )
        )
    return Config(bindings=bindings, source=source)


def add_macros(base: bytes, additions: list[tuple[Chord, str]]) -> bytes:
    """Append macro bindings to a base v7 `.cfg`.

    The output keeps the base header verbatim except for the file length
    (bytes 2-3) and chord count (bytes 8-9). Records are kept sorted by combo
    value, and new macro table entries are appended after the existing table.
    """
    cfg = parse_cfg(base)
    data = bytearray(base)

    records_end = HEADER_SIZE + cfg.num_chords * RECORD_SIZE
    existing_table = bytes(data[records_end:])

    used = {r.combo for r in cfg.records}

    new_entries = b""
    new_records = b""
    for chord, text in additions:
        combo = chord_to_combo(chord)
        if combo in used:
            raise ValueError(f"chord already bound in base config: {chord.chord_id}")
        if combo == 0:
            raise ValueError(f"chord has no keys: {chord.chord_id}")
        offset = len(existing_table) + len(new_entries)
        new_entries += macro_encode(text)
        new_records += (
            struct.pack("<I", combo)
            + bytes([OP_MACRO])
            + struct.pack("<H", offset)
            + b"\x00"
        )
        used.add(combo)

    # Merge existing and new records, sorted by combo (u32 LE).
    existing_records = bytes(data[HEADER_SIZE:records_end])
    all_records = existing_records + new_records
    chunks = [all_records[i : i + RECORD_SIZE] for i in range(0, len(all_records), RECORD_SIZE)]
    chunks.sort(key=lambda ch: struct.unpack_from("<I", ch, 0)[0])
    sorted_records = b"".join(chunks)

    out = bytearray(
        bytes(data[:HEADER_SIZE])
        + sorted_records
        + existing_table
        + new_entries
    )

    # Update file length (bytes 2-3) and chord count (bytes 8-9).
    struct.pack_into("<H", out, 2, len(out))
    struct.pack_into("<H", out, 8, cfg.num_chords + len(additions))
    return bytes(out)


def replace_macros(base: bytes, replacements: list[tuple[Chord, str]]) -> bytes:
    """Reassign existing chords in a base v7 `.cfg` to new macro text.

    Each replacement is a chord already bound in `base`; its record is swapped
    for a macro record emitting the new text. Everything else (header, other
    records, existing macro table entries) is preserved byte-for-byte.
    """
    cfg = parse_cfg(base)
    data = bytearray(base)

    records_end = HEADER_SIZE + cfg.num_chords * RECORD_SIZE
    existing_table = bytes(data[records_end:])
    existing_combos = {r.combo for r in cfg.records}

    rep_map: dict[int, str] = {}
    for chord, text in replacements:
        combo = chord_to_combo(chord)
        if combo == 0:
            raise ValueError(f"chord has no keys: {chord.chord_id}")
        if combo not in existing_combos:
            raise ValueError(
                f"chord not bound in base config: {chord.chord_id}"
            )
        rep_map[combo] = text

    kept = [
        bytes(data[HEADER_SIZE + i * RECORD_SIZE : HEADER_SIZE + (i + 1) * RECORD_SIZE])
        for i, r in enumerate(cfg.records)
        if r.combo not in rep_map
    ]

    new_entries = b""
    new_records = b""
    for combo, text in rep_map.items():
        offset = len(existing_table) + len(new_entries)
        new_entries += macro_encode(text)
        new_records += (
            struct.pack("<I", combo)
            + bytes([OP_MACRO])
            + struct.pack("<H", offset)
            + b"\x00"
        )

    all_records = b"".join(kept) + new_records
    chunks = [
        all_records[i : i + RECORD_SIZE] for i in range(0, len(all_records), RECORD_SIZE)
    ]
    chunks.sort(key=lambda ch: struct.unpack_from("<I", ch, 0)[0])
    sorted_records = b"".join(chunks)

    out = bytearray(
        bytes(data[:HEADER_SIZE]) + sorted_records + existing_table + new_entries
    )
    struct.pack_into("<H", out, 2, len(out))
    struct.pack_into("<H", out, 8, cfg.num_chords)
    return bytes(out)


# --- CSV/config -> .cfg encoder -------------------------------------------

_MOD_BITS = {
    "LCtrl": 0x01, "LShift": 0x02, "LAlt": 0x04, "LGUI": 0x08,
    "RCtrl": 0x10, "RShift": 0x20, "RAlt": 0x40, "RGUI": 0x80,
}
_NAME_TO_KEY = {name: key for key, name in _KEYCODE_NAME.items()}
_NAME_TO_KEY["Return"] = 0x28  # tuner docs also accept <Return>
_SYSTEM_IDS = {text: cid for cid, text in SYSTEM_ACTIONS.items()}
_MOUSE_IDS = {"Left": 1, "Right": 2, "Middle": 4}


def _base_key(ch: str) -> int | None:
    """The base (unshifted) HID keycode for a character, ignoring case."""
    if ch in _CHAR_TO_KEY:
        return _CHAR_TO_KEY[ch]
    if ch in _SHIFTED_CHARS:
        return _CHAR_TO_KEY[_SHIFTED_CHARS[ch]]
    if ch.isalpha():
        return _CHAR_TO_KEY[ch.lower()]
    return None


def _encode_content(content: str, mod: int) -> list[tuple[int, int]]:
    """Encode the inside of a '<Mod>...</Mod>' region into (mod, key) commands."""
    out: list[tuple[int, int]] = []
    i = 0
    n = len(content)
    while i < n:
        if content[i] == "<":
            j = content.find(">", i)
            if j == -1:
                raise ValueError(f"unterminated key tag: {content!r}")
            name = content[i + 1 : j]
            key = _NAME_TO_KEY.get(name)
            if key is None:
                raise ValueError(f"unknown key tag: <{name}>")
            out.append((mod, key))
            i = j + 1
        else:
            k = content.find("<", i)
            if k == -1:
                k = n
            for ch in content[i:k]:
                key = _base_key(ch)
                if key is None:
                    raise ValueError(f"cannot encode character: {ch!r}")
                out.append((mod, key))
            i = k
    return out


def _split_commands(inner: str) -> list[tuple[int, int]]:
    """Split a '[KB]...' inner string into (modifier, keycode) commands.

    Mirrors the tuner's action syntax: '<Mod>x</Mod>' applies the modifier to
    each key in the region, standalone '<Key>' tags emit that key unmodified,
    and everything else is literal text.
    """
    out: list[tuple[int, int]] = []
    i = 0
    n = len(inner)
    while i < n:
        if inner[i] == "<":
            j = inner.find(">", i)
            if j == -1:
                raise ValueError(f"unterminated tag in action: {inner!r}")
            name = inner[i + 1 : j]
            if name in _MOD_BITS:
                closing = f"</{name}>"
                end = inner.find(closing, j + 1)
                if end != -1:
                    out.extend(_encode_content(inner[j + 1 : end], _MOD_BITS[name]))
                    i = end + len(closing)
                    continue
            key = _NAME_TO_KEY.get(name)
            if key is None:
                raise ValueError(f"unknown key tag: <{name}>")
            out.append((0, key))
            i = j + 1
        else:
            k = inner.find("<", i)
            if k == -1:
                k = n
            for ch in inner[i:k]:
                if ch in _CHAR_TO_KEY:
                    out.append((0, _CHAR_TO_KEY[ch]))
                elif ch in _SHIFTED_CHARS:
                    out.append(
                        (_MOD_BITS["RShift"], _CHAR_TO_KEY[_SHIFTED_CHARS[ch]])
                    )
                elif ch.isalpha():
                    out.append((_MOD_BITS["RShift"], _CHAR_TO_KEY[ch.lower()]))
                else:
                    raise ValueError(f"cannot encode character: {ch!r}")
            i = k
    return out


def action_to_record(
    raw_action: str,
) -> tuple[int, int, int, list[tuple[int, int, int]] | None]:
    """Encode one CSV action string into a .cfg record.

    Returns (command_type, data0, data1, macro_entries). `macro_entries` is
    None for non-macro records; for macro records it is the list of
    (opcode, data0, data1) commands to store in the macro table.
    """
    if raw_action.startswith("[SYS]"):
        if raw_action in _SYSTEM_IDS:
            return OP_SYSTEM, _SYSTEM_IDS[raw_action], 0, None
        m = re.match(r"^\[SYS\]\[Mouse\]<Mouse (Left|Right|Middle) Click>$", raw_action)
        if m:
            return OP_MOUSE, _MOUSE_IDS[m.group(1)], 0, None
        m = re.match(r"^\[SYS\]\[Delay\]<(\d+)ms>$", raw_action)
        if m:
            value = int(m.group(1)) // 10
            return OP_DELAY, value & 0xFF, (value >> 8) & 0xFF, None
        raise ValueError(f"unsupported system action: {raw_action!r}")

    if not raw_action.startswith("[KB]"):
        mouse_hold = re.match(
            r"^\[MS\]Down: (Left|Right|Middle)\r?\n"
            r"\[DLY\](\d+)ms\[MS\]Release$",
            raw_action,
        )
        if mouse_hold:
            button = {"Left": 1, "Right": 2, "Middle": 4}[mouse_hold.group(1)]
            delay = int(mouse_hold.group(2))
            if delay == 0 or delay % 10 or delay > 655350:
                raise ValueError(f"unsupported mouse hold delay: {delay}ms")
            delay_units = delay // 10
            return OP_MACRO, 0, 0, [
                (OP_MOUSE, button, 0),
                (OP_DELAY, delay_units & 0xFF, (delay_units >> 8) & 0xFF),
                (OP_MOUSE, 0, 0),
            ]
        raise ValueError(f"unsupported action: {raw_action!r}")

    commands = _split_commands(raw_action[4:])
    if not commands:
        raise ValueError(f"empty keyboard action: {raw_action!r}")
    if len(commands) == 1:
        mod, key = commands[0]
        return OP_KEYBOARD, mod & 0xFF, key & 0xFF, None
    return OP_MACRO, 0, 0, [
        (OP_KEYBOARD, mod, key) for mod, key in commands
    ]


def config_to_cfg(config: Config, base: bytes) -> bytes:
    """Rebuild a .cfg from a Config, reusing the header/settings from `base`.

    The CSV/config is authoritative for the bindings: every binding becomes a
    record, sorted by combo. The base .cfg contributes only the header (tag,
    settings, fixed lookup table), which is preserved verbatim except for the
    chord count (bytes 8-9) and file length (bytes 2-3).
    """
    base_cfg = parse_cfg(base)

    records: list[tuple[int, int, int, int]] = []
    entries: list[list[tuple[int, int, int]] | None] = []
    for b in config.bindings:
        combo = chord_to_combo(b.chord)
        if combo == 0:
            raise ValueError(f"chord has no keys: {b.raw_action!r}")
        ctype, d0, d1, macro = action_to_record(b.raw_action)
        records.append((combo, ctype, d0, d1))
        entries.append(macro)

    ordered = sorted(zip(records, entries), key=lambda pair: pair[0][0])

    table = bytearray()
    out_records = bytearray()
    for (combo, ctype, d0, d1), macro in ordered:
        if ctype == OP_MACRO:
            offset = len(table)
            for op, data0, data1 in macro:
                table += bytes([op, data0 & 0xFF, data1 & 0xFF, 0])
            table += b"\x00\x00\x00\x00"
            d0, d1 = offset & 0xFF, (offset >> 8) & 0xFF
        out_records += struct.pack("<I", combo) + bytes([ctype, d0, d1, 0])

    out = bytearray(bytes(base[:HEADER_SIZE]) + bytes(out_records) + bytes(table))
    struct.pack_into("<H", out, 2, len(out))
    struct.pack_into("<H", out, 8, len(records))
    return bytes(out)
