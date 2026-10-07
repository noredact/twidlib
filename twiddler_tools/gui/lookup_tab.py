"""Chord Lookup tab: search by chord/pairing, or pick special keys."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ..lookup import (
    find_by_chord,
    find_by_finger_key,
    find_by_segment_names,
    find_by_system_action,
    find_by_text,
    system_actions,
)
from ..model import (
    Chord,
    FingerKey,
    ThumbKey,
    display_action,
    format_chord,
    parse_chord_spec,
)
from ..render import active_keys
from ..special_keys import SPECIAL_KEYS
from .keyboard_widget import KeyboardWidget


class LookupTab(QWidget):
    def __init__(self, config, inbox, parent=None):
        super().__init__(parent)
        self.config = config
        self.inbox = inbox

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Lookup chord:"))
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("e.g. F2M 3R 4R  or  ing")
        self.query_edit.textChanged.connect(self.search)
        top.addWidget(self.query_edit, 1)
        self.mirror_cb = QCheckBox("Mirror")
        self.mirror_cb.toggled.connect(self.toggle_mirror)
        top.addWidget(self.mirror_cb)
        layout.addLayout(top)

        special_row = QHBoxLayout()
        special_row.addWidget(QLabel("Special keys / actions:"))
        self.special_combo = QComboBox()
        self.special_combo.currentIndexChanged.connect(self.show_special)
        special_row.addWidget(self.special_combo, 1)
        layout.addLayout(special_row)

        self._populate_special_combo()

        body = QHBoxLayout()

        results_col = QVBoxLayout()
        results_header = QHBoxLayout()
        results_header.addWidget(QLabel("Outputs:"))
        results_header.addStretch(1)
        results_col.addLayout(results_header)

        self.results = QListWidget()
        self.results.currentRowChanged.connect(self.show_selected)
        results_col.addWidget(self.results, 1)
        body.addLayout(results_col, 1)

        body.addStretch(1)  # keep the Clear button flush against the keymap

        self.keyboard = KeyboardWidget()
        self.keyboard.set_selectable(True)
        self.keyboard.selection_changed.connect(self._on_keyboard_click)

        clear_col = QVBoxLayout()
        self._clear_spacer = QSpacerItem(
            0,
            int(self.keyboard.row_center_y(2) - 14),
            QSizePolicy.Minimum,
            QSizePolicy.Fixed,
        )
        clear_col.addItem(self._clear_spacer)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_highlight)
        clear_col.addWidget(self.clear_btn)
        clear_col.addStretch(1)
        body.addLayout(clear_col, 0)

        kb_col = QVBoxLayout()
        kb_col.addWidget(self.keyboard, 1)
        body.addLayout(kb_col, 2)

        layout.addLayout(body, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def set_scale(self, factor: float) -> None:
        self.keyboard.set_scale(factor)
        self._clear_spacer.changeSize(
            0,
            int(self.keyboard.row_center_y(2) - 14),
            QSizePolicy.Minimum,
            QSizePolicy.Fixed,
        )
        self.layout().invalidate()

    def refresh_config(self, config) -> None:
        self.config = config
        self._populate_special_combo()
        self.search()

    def toggle_mirror(self, checked: bool) -> None:
        self.keyboard.set_mirror(checked)

    def search(self) -> None:
        self.keyboard.clear()  # typing replaces any manually highlighted keys
        query = self.query_edit.text().strip()
        if not query:
            self.results.clear()
            self.keyboard.clear()
            self.status.setText("")
            return

        chord = self._try_parse_chord(query)
        if chord is not None:
            matches = find_by_chord(self.config, chord)
            if matches:
                self._populate(
                    matches, f"{len(matches)} binding(s) on chord {format_chord(chord)}."
                )
            else:
                self.results.clear()
                self.keyboard.clear()
                self.status.setText(
                    f"No binding on chord \u201c{format_chord(chord)}\u201d."
                )
            return

        matches = find_by_text(self.config, query)
        if matches:
            self._populate(
                matches, f"{len(matches)} chord(s) type \u201c{query}\u201d."
            )
        else:
            self.results.clear()
            pending = self.inbox.find(query)
            if pending is not None:
                self.status.setText(
                    f"Not on the device yet \u2014 \u201c{query}\u201d is in your export queue (pending)."
                )
            else:
                self.status.setText(
                    f"No chord types \u201c{query}\u201d on the device or in your export queue."
                )
            self.keyboard.clear()

    def show_special(self, index: int) -> None:
        data = self.special_combo.itemData(index)
        if data is None:
            return
        what = self.special_combo.itemText(index)
        if data[0] == "key":
            matches = find_by_segment_names(self.config, data[1])
        elif data[0] == "system":
            matches = find_by_system_action(self.config, data[1], data[2])
        else:  # "finger" (mouse button included in the chord)
            matches = find_by_finger_key(self.config, data[1], data[2])

        if matches:
            self._populate(matches, f"{len(matches)} chord(s) for {what}.")
        else:
            self.results.clear()
            self.keyboard.clear()
            self.status.setText(f"No chord bound to {what} on your device.")

    def _try_parse_chord(self, query: str):
        try:
            return parse_chord_spec(query)
        except ValueError:
            return None

    def _populate_special_combo(self) -> None:
        self.special_combo.blockSignals(True)
        self.special_combo.clear()
        self.special_combo.addItem("\u2014 select \u2014", None)
        self.special_combo.addItem("Mouse Left Click", ("finger", 0, "L"))
        self.special_combo.addItem("Mouse Middle Click", ("finger", 0, "M"))
        self.special_combo.addItem("Mouse Right Click", ("finger", 0, "R"))
        for label, names in SPECIAL_KEYS:
            self.special_combo.addItem(label, ("key", names))
        for subsystem, command in system_actions(self.config):
            self.special_combo.addItem(
                f"System: {command}", ("system", subsystem, command)
            )
        self.special_combo.setCurrentIndex(0)
        self.special_combo.blockSignals(False)

    def _populate(self, matches, status_text: str, select_first: bool = True) -> None:
        self.results.clear()
        for b in matches:
            label = f"{display_action(b.raw_action)}  \u2014  {format_chord(b.chord)}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, b)
            self.results.addItem(item)
        self.status.setText(status_text)
        if select_first:
            self.results.setCurrentRow(0)

    def _on_keyboard_click(self) -> None:
        thumbs, fingers = self.keyboard.selected()
        if not thumbs and not fingers:
            self.results.clear()
            self.status.setText("")
            return
        chord = Chord(
            fingers=frozenset(FingerKey(r, c) for r, c in fingers),
            thumbs=frozenset(ThumbKey(i) for i in thumbs),
        )
        matches = find_by_chord(self.config, chord)
        # Clear the search field so it does not contradict the clicked chord.
        self.query_edit.blockSignals(True)
        self.query_edit.clear()
        self.query_edit.blockSignals(False)
        if matches:
            self._populate(
                matches,
                f"{len(matches)} binding(s) on chord {format_chord(chord)}.",
                select_first=False,
            )
        else:
            self.results.clear()
            self.status.setText(f"No binding on chord \u201c{format_chord(chord)}\u201d.")

    def clear_highlight(self) -> None:
        self.keyboard.clear()
        self.results.clear()
        self.status.setText("")
        self.query_edit.blockSignals(True)
        self.query_edit.clear()
        self.query_edit.blockSignals(False)

    def show_selected(self, row: int) -> None:
        if row < 0:
            self.keyboard.clear()
            return
        item = self.results.item(row)
        binding = item.data(Qt.UserRole)
        ak = active_keys(binding.chord)
        self.keyboard.set_active_keys(ak.thumbs, ak.fingers)
