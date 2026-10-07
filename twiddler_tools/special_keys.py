"""Catalog of Twiddler standalone special-key tags.

Sourced from the official tuner documentation:
  https://www.mytwiddler.com/doc/doku.php?id=tuner_special_keys
  https://www.mytwiddler.com/doc/doku.php?id=tuner_key_syntax

Each entry maps a human-readable label to the set of tag names that can appear
inside a '[KB]<Name>' action. Some entries carry aliases: the docs call the
Enter/Return key '<Return>', but config exports also use '<Enter>', so both
names are accepted.
"""

SPECIAL_KEYS: list[tuple[str, frozenset[str]]] = [
    ("Return (Enter)", frozenset({"Return", "Enter"})),
    ("Escape", frozenset({"Escape"})),
    ("Backspace", frozenset({"Backspace"})),
    ("Tab", frozenset({"Tab"})),
    ("Caps Lock", frozenset({"CapsLock"})),
    *[(f"F{i}", frozenset({f"F{i}"})) for i in range(1, 25)],
    ("Print Screen", frozenset({"PrintScreen"})),
    ("Scroll Lock", frozenset({"ScrollLock"})),
    ("Pause", frozenset({"Pause"})),
    ("Insert", frozenset({"Insert"})),
    ("Home", frozenset({"Home"})),
    ("Page Up", frozenset({"PageUp"})),
    ("Delete (Forward)", frozenset({"Delete"})),
    ("End", frozenset({"End"})),
    ("Page Down", frozenset({"PageDown"})),
    ("Right Arrow", frozenset({"RightArrow"})),
    ("Left Arrow", frozenset({"LeftArrow"})),
    ("Down Arrow", frozenset({"DownArrow"})),
    ("Up Arrow", frozenset({"UpArrow"})),
    ("Num Lock", frozenset({"NumLock"})),
    ("Application", frozenset({"Application"})),
    ("Keypad /", frozenset({"KP/"})),
    ("Keypad *", frozenset({"KP*"})),
    ("Keypad -", frozenset({"KP-"})),
    ("Keypad +", frozenset({"KP+"})),
    ("Keypad Enter", frozenset({"KPEnter"})),
    *[(f"Keypad {i}", frozenset({f"KP{i}"})) for i in range(10)],
    ("Keypad .", frozenset({"KP."})),
    ("Keypad =", frozenset({"KP="})),
]
