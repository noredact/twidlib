"""Smoke tests for the PySide6 GUI (skipped when PySide6 is unavailable).

Run under a standard CPython venv with PySide6 installed, e.g.:

    .venv-gui/Scripts/python.exe -m pytest tests/test_gui_smoke.py
"""

import os

# Must be set before QtWidgets is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from twiddler_tools import cfg_io  # noqa: E402
from twiddler_tools.csv_io import parse_csv  # noqa: E402
from twiddler_tools.gui.app import MainWindow  # noqa: E402
from twiddler_tools.gui.keyboard_widget import KeyboardWidget  # noqa: E402
from twiddler_tools.inbox import Inbox  # noqa: E402
from twiddler_tools.model import (  # noqa: E402
    Binding,
    Chord,
    Config,
    FingerKey,
    parse_action,
    parse_chord_spec,
)

SAMPLE = Path(__file__).resolve().parent.parent / "test_config.csv"


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_constructs(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    assert win.inbox_tab is not None
    assert win.lookup_tab is not None
    assert win.config_tab is not None
    assert win.chord_editor_tab is not None
    assert win.centralWidget().count() == 4


def test_lookup_or_shows_chord(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("or")
    assert win.lookup_tab.results.count() == 1
    ak = win.lookup_tab.keyboard
    assert ak._fingers == frozenset({(2, "M"), (3, "R"), (4, "R")})
    assert ak._thumbs == frozenset()


def test_lookup_ing_shows_chord(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("ing")
    assert win.lookup_tab.results.count() == 1
    assert win.lookup_tab.keyboard._fingers == frozenset({(4, "L")})


def test_lookup_t_shows_chord(app, tmp_path):
    # Regression: "t" was parsed as a (thumb) chord token and never text-searched.
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("t")
    assert win.lookup_tab.results.count() == 1
    assert "[KB]t" in win.lookup_tab.results.item(0).text()
    assert win.lookup_tab.keyboard._fingers == frozenset({(2, "M"), (3, "M")})


def test_lookup_pending_inbox_hint(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("zz")
    assert win.lookup_tab.results.count() == 0
    assert "in your export queue" in win.lookup_tab.status.text()


def test_mirror_toggle(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("or")
    assert win.lookup_tab.keyboard._mirror is False
    win.lookup_tab.mirror_cb.setChecked(True)
    assert win.lookup_tab.keyboard._mirror is True


def test_inbox_flags_on_device(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.inbox_tab.text_edit.setText("or")
    win.inbox_tab.add()
    assert "already on your device" in win.inbox_tab.flag_label.text()
    assert win.inbox_tab.table.rowCount() == 0


def test_inbox_add_with_chord_spec(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.inbox_tab.text_edit.setText("zz")
    win.inbox_tab.chord_edit.setText("T12 F1LM 2MR")
    win.inbox_tab.add()
    item = win.inbox_tab.inbox.find("zz")
    assert item.chord_id == "T12 F1LM 2MR"
    assert win.inbox_tab.table.rowCount() == 1


def test_inbox_flags_duplicate_text(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.inbox_tab.text_edit.setText("zz")
    win.inbox_tab.add()
    assert win.inbox_tab.table.rowCount() == 1
    win.inbox_tab.text_edit.setText("zz")  # duplicate output text
    win.inbox_tab.add()
    assert "already in your export queue" in win.inbox_tab.flag_label.text()
    assert win.inbox_tab.table.rowCount() == 1


def test_inbox_reassign_used_chord(app, tmp_path, monkeypatch):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.inbox_tab.text_edit.setText("zz")
    win.inbox_tab.chord_edit.setText("F2M 3R 4R")  # already bound to "or"

    # Cancelling the confirmation adds nothing.
    monkeypatch.setattr(win.inbox_tab, "_confirm_reassign", lambda used, text: False)
    win.inbox_tab.add()
    assert inbox.find("zz") is None
    assert win.inbox_tab.table.rowCount() == 0

    # Confirming queues it as a reassignment.
    monkeypatch.setattr(win.inbox_tab, "_confirm_reassign", lambda used, text: True)
    win.inbox_tab.add()
    item = inbox.find("zz")
    assert item is not None
    assert item.override is True
    assert item.chord_id == "F2M 3R 4R"
    assert win.inbox_tab.table.rowCount() == 1


def test_inbox_flags_duplicate_chord_between_items(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.inbox_tab.text_edit.setText("aa")
    win.inbox_tab.chord_edit.setText("T12 F1LM 2MR")  # free on device
    win.inbox_tab.add()
    assert win.inbox_tab.table.rowCount() == 1
    win.inbox_tab.text_edit.setText("bb")
    win.inbox_tab.chord_edit.setText("T12 F1LM 2MR")  # same chord again
    win.inbox_tab.add()
    assert "already defined in your queue" in win.inbox_tab.flag_label.text()
    assert win.inbox_tab.table.rowCount() == 1


def test_lookup_by_chord_notation(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    win.lookup_tab.query_edit.setText("F2M 3R 4R")
    assert win.lookup_tab.results.count() == 1
    assert "[KB]or" in win.lookup_tab.results.item(0).text()


def test_special_key_dropdown_capslock(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    combo = win.lookup_tab.special_combo
    idx = combo.findText("Caps Lock")
    assert idx >= 0
    combo.setCurrentIndex(idx)
    assert win.lookup_tab.results.count() == 1
    assert win.lookup_tab.keyboard._fingers == frozenset({(1, "R"), (3, "R"), (4, "R")})


def test_special_key_dropdown_system(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    combo = win.lookup_tab.special_combo
    idx = combo.findText("System: Sleep Sleep Now")
    assert idx >= 0
    combo.setCurrentIndex(idx)
    assert win.lookup_tab.results.count() == 1
    assert win.lookup_tab.keyboard._thumbs == frozenset({0, 2, 3})


def test_mouse_click_dropdown(app, tmp_path):
    config = Config(
        bindings=[
            Binding(
                chord=Chord(
                    fingers=frozenset({FingerKey(0, "L"), FingerKey(1, "M")})
                ),
                action=parse_action("[KB]email"),
                raw_thumbs="",
                raw_fingers="0L 1M",
                raw_action="[KB]email",
            )
        ]
    )
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    combo = win.lookup_tab.special_combo
    idx = combo.findText("Mouse Left Click")
    assert idx >= 0
    combo.setCurrentIndex(idx)
    assert win.lookup_tab.results.count() == 1
    assert win.lookup_tab.keyboard._fingers == frozenset({(0, "L"), (1, "M")})


def test_export_json(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    out = tmp_path / "out.json"
    summary = win.config_tab.export_json_to(str(out))
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["chords"]) > 0
    assert "Skipped" in summary  # the custom config has multi-column rows


def test_export_cfg_marks_exported(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    inbox.add("zz", chord_id="F2R 2M")
    inbox.add("yy", chord_id="F1L 1M")
    base = (
        Path(__file__).resolve().parent.parent
        / "sample_config_files"
        / "test_config1.cfg"
    )
    out = tmp_path / "out.cfg"
    summary = win.inbox_tab.export_cfg_to(str(base), str(out))
    assert out.exists()
    assert "2 new chord" in summary
    assert inbox.find("zz").status == "exported"
    assert inbox.find("yy").status == "exported"
    macros = cfg_io.macros_in(out.read_bytes())
    assert macros[cfg_io.chord_to_combo(parse_chord_spec("F2R 2M"))] == "zz"
    assert macros[cfg_io.chord_to_combo(parse_chord_spec("F1L 1M"))] == "yy"


def test_export_cfg_replaces_override(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    inbox.add("zz", chord_id="F4L", override=True)  # F4L currently types "ing"
    base = (
        Path(__file__).resolve().parent.parent
        / "sample_config_files"
        / "test_config1.cfg"
    )
    out = tmp_path / "out.cfg"
    summary = win.inbox_tab.export_cfg_to(str(base), str(out))
    assert out.exists()
    assert "reassigned" in summary
    macros = cfg_io.macros_in(out.read_bytes())
    assert macros[cfg_io.chord_to_combo(parse_chord_spec("F4L"))] == "zz"
    assert inbox.find("zz").status == "exported"
    # Chord count unchanged: one record was swapped, not added.
    assert cfg_io.parse_cfg(out.read_bytes()).num_chords == 145


def test_chord_editor_adds_to_queue(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    ed = win.chord_editor_tab
    ed.text_edit.setText("zz")
    ed.keyboard.set_active_keys(
        thumbs=frozenset({1, 2}),
        fingers=frozenset({(1, "L"), (1, "M"), (2, "M"), (2, "R")}),
    )
    ed.add_to_queue()
    item = inbox.find("zz")
    assert item is not None
    assert item.chord_id == "T12 F1LM 2MR"
    assert win.inbox_tab.table.rowCount() == 1  # queue refreshed via signal
    # Fields/GUI reset, ready for the next chord.
    assert ed.text_edit.text() == ""
    assert ed.keyboard.selected() == (frozenset(), frozenset())


def test_chord_editor_reassigns_used_chord(app, tmp_path, monkeypatch):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    ed = win.chord_editor_tab
    ed.text_edit.setText("zz")
    ed.keyboard.set_active_keys(fingers=frozenset({(2, "M"), (3, "R"), (4, "R")}))

    # Cancelling adds nothing.
    monkeypatch.setattr(ed, "_confirm_reassign", lambda used, text: False)
    ed.add_to_queue()
    assert inbox.find("zz") is None

    # Confirming queues it as a reassignment.
    monkeypatch.setattr(ed, "_confirm_reassign", lambda used, text: True)
    ed.add_to_queue()
    item = inbox.find("zz")
    assert item is not None
    assert item.override is True


def test_chord_editor_reserved_panel(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    ed = win.chord_editor_tab
    ed.keyboard.set_active_keys(fingers=frozenset({(2, "M"), (3, "R"), (4, "R")}))
    ed._update_reserved()
    texts = [
        ed.reserved_list.item(i).text() for i in range(ed.reserved_list.count())
    ]
    assert any("[KB]or" in t for t in texts)


def test_lookup_click_shows_output(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    lt = win.lookup_tab
    lt.keyboard.resize(400, 720)
    _, finger_rects, _ = lt.keyboard._geometry()
    for key in [(2, "M"), (3, "R"), (4, "R")]:
        rect = finger_rects[key]
        QTest.mouseClick(lt.keyboard, Qt.LeftButton, pos=rect.center().toPoint())
    assert lt.results.count() == 1
    assert "[KB]or" in lt.results.item(0).text()


def test_lookup_clear_unhighlights(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    lt = win.lookup_tab
    lt.keyboard.set_active_keys(fingers=frozenset({(2, "M"), (3, "R"), (4, "R")}))
    lt.clear_highlight()
    assert lt.keyboard.selected() == (frozenset(), frozenset())
    assert lt.results.count() == 0


def test_lookup_typing_replaces_highlight(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    lt = win.lookup_tab
    lt.keyboard.set_active_keys(fingers=frozenset({(1, "L")}))
    lt.query_edit.setText("or")
    _, fingers = lt.keyboard.selected()
    assert fingers == frozenset({(2, "M"), (3, "R"), (4, "R")})


def test_lookup_add_output_hands_off_to_editor(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    lt = win.lookup_tab

    # The button starts disabled and enables once keys are highlighted.
    assert lt.add_output_btn.isEnabled() is False
    lt.keyboard.set_active_keys(fingers=frozenset({(2, "R"), (2, "M")}))
    lt._update_add_btn()
    assert lt.add_output_btn.isEnabled() is True

    lt.add_output_btn.click()

    assert win.tabs.currentWidget() is win.chord_editor_tab
    ed = win.chord_editor_tab
    assert ed.keyboard.selected() == (frozenset(), frozenset({(2, "R"), (2, "M")}))
    assert ed.add_btn.text() == "Add to queue"
    assert ed.text_edit.text() == ""


def test_export_queue_table_columns(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("or")  # on device
    inbox.add("zz")  # pending
    win = MainWindow(config, inbox)
    t = win.inbox_tab.table
    assert t.columnCount() == 5
    assert t.rowCount() == 2
    rows = {t.item(r, 0).text(): t.item(r, 2).text() for r in range(t.rowCount())}
    assert rows["or"] == "on device"
    assert rows["zz"] == "pending"


def test_chord_editor_adds_space(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    ed = win.chord_editor_tab
    ed.text_edit.setText(" ")
    ed.keyboard.set_active_keys(
        thumbs=frozenset({1, 2}),
        fingers=frozenset({(1, "L"), (1, "M"), (2, "M"), (2, "R")}),
    )
    ed.add_to_queue()
    item = inbox.find(" ")
    assert item is not None
    assert item.chord_id == "T12 F1LM 2MR"
    # Queue shows the space clearly rather than a blank cell.
    assert win.inbox_tab.table.item(0, 0).text() == "[sp]"


def test_edit_from_queue_renames(app, tmp_path):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz", chord_id="T12 F1LM 2MR")
    win = MainWindow(config, inbox)
    win.inbox_tab._edit_text("zz")  # emits edit_requested -> load + switch tab
    ed = win.chord_editor_tab
    assert ed.text_edit.text() == "zz"
    assert ed._edit_text == "zz"
    ed.text_edit.setText("yy")  # rename; chord unchanged
    ed.add_to_queue()
    assert inbox.find("zz") is None
    assert inbox.find("yy") is not None
    assert inbox.find("yy").chord_id == "T12 F1LM 2MR"
    assert ed._edit_text is None  # edit mode reset


def test_edit_from_queue_overwrite_text_collision(app, tmp_path, monkeypatch):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz", chord_id="T12 F1LM 2MR")
    inbox.add("yy")
    win = MainWindow(config, inbox)
    win.inbox_tab._edit_text("zz")
    ed = win.chord_editor_tab
    ed.text_edit.setText("yy")  # collides with existing "yy"
    monkeypatch.setattr(ed, "_confirm_overwrite", lambda msg: True)
    ed.add_to_queue()
    assert inbox.find("zz") is None
    assert inbox.find("yy").chord_id == "T12 F1LM 2MR"


def test_edit_cancel_keeps_original(app, tmp_path, monkeypatch):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz", chord_id="T12 F1LM 2MR")
    inbox.add("yy")
    win = MainWindow(config, inbox)
    win.inbox_tab._edit_text("zz")
    ed = win.chord_editor_tab
    ed.text_edit.setText("yy")
    monkeypatch.setattr(ed, "_confirm_overwrite", lambda msg: False)
    ed.add_to_queue()
    assert inbox.find("zz") is not None
    assert inbox.find("zz").chord_id == "T12 F1LM 2MR"  # unchanged
    assert inbox.find("yy").chord_id is None


def test_remove_exported_warns(app, tmp_path, monkeypatch):
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz", chord_id="T12 F1LM 2MR")
    inbox.mark_exported("zz")
    win = MainWindow(config, inbox)
    called = []
    monkeypatch.setattr(
        win.inbox_tab, "_confirm_remove_exported", lambda t: called.append(t) or False
    )
    win.inbox_tab._remove_text("zz")
    assert called == ["zz"]
    assert inbox.find("zz") is not None  # cancelled, still present
    monkeypatch.setattr(win.inbox_tab, "_confirm_remove_exported", lambda t: True)
    win.inbox_tab._remove_text("zz")
    assert inbox.find("zz") is None


def test_clear_on_device(app, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Yes)
    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("or")  # already bound on the device in the sample config
    inbox.add("zz")
    win = MainWindow(config, inbox)
    win.inbox_tab.clear_on_device()
    assert inbox.find("or") is None
    assert inbox.find("zz") is not None


def test_keyboard_click_toggles_keys(app):
    widget = KeyboardWidget()
    widget.set_selectable(True)
    widget.resize(400, 720)
    _, finger_rects, thumb_rects = widget._geometry()

    rect = finger_rects[(1, "L")]
    center = rect.center().toPoint()
    QTest.mouseClick(widget, Qt.LeftButton, pos=center)
    thumbs, fingers = widget.selected()
    assert (1, "L") in fingers
    assert (1, "R") not in fingers

    QTest.mouseClick(widget, Qt.LeftButton, pos=center)  # deselect
    _, fingers = widget.selected()
    assert (1, "L") not in fingers

    # Thumb 0 is a circle; clicking its centre toggles it.
    cx, cy, _ = thumb_rects[0]
    QTest.mouseClick(widget, Qt.LeftButton, pos=QPoint(round(cx), round(cy)))
    thumbs, _ = widget.selected()
    assert 0 in thumbs


def test_keyboard_set_scale_resizes(app):
    widget = KeyboardWidget()
    assert widget.sizeHint().height() == 600
    assert widget.row_center_y(2) == pytest.approx(174.0)

    widget.set_scale(0.6)
    assert widget.sizeHint().width() == 216
    assert widget.sizeHint().height() == 360
    assert widget.row_center_y(2) == pytest.approx(174.0 * 0.6)


def test_config_scale_combo_updates_keymaps(app, tmp_path, monkeypatch):
    from twiddler_tools.gui import config_tab

    monkeypatch.setattr(config_tab, "load_gui_scale", lambda: 1.0)
    monkeypatch.setattr(config_tab, "save_gui_scale", lambda factor: None)

    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)
    combo = win.config_tab.size_combo
    emitted = []
    win.config_tab.scale_changed.connect(emitted.append)

    combo.setCurrentIndex(0)  # Small
    assert emitted[-1] == pytest.approx(0.6)
    assert win.chord_editor_tab.keyboard.sizeHint().height() == 360
    assert win.lookup_tab.keyboard.sizeHint().height() == 360


def test_csv_to_cfg_exports(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    config = parse_csv(SAMPLE.read_text(encoding="utf-8-sig"))
    inbox = Inbox(tmp_path / "inbox.json")
    win = MainWindow(config, inbox)

    base = tmp_path / "base.cfg"
    base.write_bytes(
        (Path(__file__).resolve().parent.parent / "test_config.cfg").read_bytes()
    )
    out = tmp_path / "out.cfg"

    def fake_open(parent, title, *args, **kwargs):
        if "CSV" in title:
            return str(SAMPLE), "CSV files (*.csv)"
        return str(base), "CFG files (*.cfg)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(fake_open))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CFG files (*.cfg)")),
    )

    win.config_tab.csv_to_cfg()

    assert out.exists()
    assert "146 chord" in win.config_tab.export_label.text()
    back = cfg_io.cfg_to_config(cfg_io.parse_cfg(out.read_bytes()))
    assert len(back.bindings) == 146
