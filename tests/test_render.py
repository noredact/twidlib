from twiddler_tools.model import Chord, FingerKey, ThumbKey
from twiddler_tools.render import active_keys, layout


def test_active_keys():
    chord = Chord(
        fingers=frozenset({FingerKey(2, "M"), FingerKey(3, "R")}),
        thumbs=frozenset({ThumbKey(1), ThumbKey(2)}),
    )
    ak = active_keys(chord)
    assert ak.thumbs == frozenset({1, 2})
    assert ak.fingers == frozenset({(2, "M"), (3, "R")})


def test_layout_static():
    l = layout()
    assert l["mouse_row"] == 0
    assert l["rows"] == (1, 2, 3, 4)
    assert l["cols"] == ("L", "M", "R")
    assert l["thumbs"] == (0, 1, 2, 3, 4)
