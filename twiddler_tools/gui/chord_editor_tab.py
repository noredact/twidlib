"""Chord Editor tab: pick keys on the keymap, type the text, add to queue."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..lookup import find_by_chord
from ..model import (
    Chord,
    FingerKey,
    ThumbKey,
    display_action,
    display_text,
    format_chord,
    parse_chord_spec,
)
from ..special_keys import SPECIAL_KEYS
from .keyboard_widget import KeyboardWidget

_MODIFIERS = ("RShift", "LShift", "LCtrl", "RCtrl", "LAlt", "RAlt", "LGUI", "RGUI")


class ChordEditorTab(QWidget):
    queue_changed = Signal()

    def __init__(self, config, inbox, parent=None):
        super().__init__(parent)
        self.config = config
        self.inbox = inbox
        self._edit_text: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Type the text to send when the chord is pressed, then click the keys:")
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("Text:"))
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("e.g. ing, or, the , or a single space")
        self.text_edit.returnPressed.connect(self.add_to_queue)
        row.addWidget(self.text_edit, 1)
        layout.addLayout(row)

        special_row = QHBoxLayout()
        special_row.addWidget(QLabel("Special keys / actions:"))
        self.special_combo = QComboBox()
        self.special_combo.activated.connect(self._insert_special)
        special_row.addWidget(self.special_combo, 1)
        layout.addLayout(special_row)
        self._populate_special_combo()

        self.keyboard = KeyboardWidget()
        self.keyboard.set_selectable(True)
        self.keyboard.selection_changed.connect(self._update_reserved)

        body = QHBoxLayout()
        body.addWidget(self.keyboard, 2)

        reserved_col = QVBoxLayout()
        reserved_col.addWidget(QLabel("Reserved outputs:"))
        self.reserved_list = QListWidget()
        reserved_col.addWidget(self.reserved_list, 1)
        body.addLayout(reserved_col, 1)

        layout.addLayout(body, 1)

        self.add_btn = QPushButton("Add to queue")
        self.add_btn.clicked.connect(self.add_to_queue)
        layout.addWidget(self.add_btn)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def set_config(self, config) -> None:
        self.config = config
        self._update_reserved()

    def set_scale(self, factor: float) -> None:
        self.keyboard.set_scale(factor)

    def _selected_chord(self):
        thumbs, fingers = self.keyboard.selected()
        if not thumbs and not fingers:
            return None
        return Chord(
            fingers=frozenset(FingerKey(r, c) for r, c in fingers),
            thumbs=frozenset(ThumbKey(i) for i in thumbs),
        )

    def load_for_edit(self, text: str) -> None:
        """Load an existing queue item into the editor for modification."""
        item = self.inbox.find(text)
        if item is None:
            return
        self._edit_text = item.text
        self.text_edit.setText(item.text)
        if item.chord_id:
            try:
                chord = parse_chord_spec(item.chord_id)
                self.keyboard.set_active_keys(
                    thumbs=frozenset(t.index for t in chord.thumbs),
                    fingers=frozenset((k.row, k.col) for k in chord.fingers),
                )
            except ValueError:
                self.keyboard.clear()
        else:
            self.keyboard.clear()
        self.add_btn.setText("Save changes")
        self._update_reserved()
        self._status(
            f"Editing \u201c{display_text(item.text)}\u201d. Change the text or chord, "
            "then click Save changes."
        )

    def _reset_edit_mode(self) -> None:
        self._edit_text = None
        self.add_btn.setText("Add to queue")

    def preload_chord(
        self,
        thumbs: frozenset[int] | set[int],
        fingers: frozenset[tuple[int, str]] | set[tuple[int, str]],
    ) -> None:
        """Start a fresh add with the given chord already highlighted.

        Used by Chord Lookup's "Add output" so the user only has to type the
        text for a chord they just verified on the keymap.
        """
        self._reset_edit_mode()
        self.text_edit.clear()
        self.keyboard.set_active_keys(thumbs=frozenset(thumbs), fingers=frozenset(fingers))
        self._update_reserved()
        self._status("Type the text to send, then click Add to queue.")
        self.text_edit.setFocus()

    def _confirm_overwrite(self, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("Already exists")
        box.setText(message)
        box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        box.button(QMessageBox.Yes).setText("Overwrite")
        return box.exec() == QMessageBox.Yes

    def _update_reserved(self) -> None:
        self.reserved_list.clear()
        chord = self._selected_chord()
        if chord is None:
            return
        for b in find_by_chord(self.config, chord):
            self.reserved_list.addItem(
                QListWidgetItem(f"{display_action(b.raw_action)}  (on device)")
            )
        for item in self.inbox.items():
            if item.chord_id:
                try:
                    if parse_chord_spec(item.chord_id) == chord:
                        self.reserved_list.addItem(
                            QListWidgetItem(f"{display_text(item.text)}  (in queue)")
                        )
                except ValueError:
                    continue

    def _populate_special_combo(self) -> None:
        self.special_combo.addItem("\u2014 insert \u2014", None)
        self.special_combo.addItem("Space", ("space", None))
        for mod in _MODIFIERS:
            self.special_combo.addItem(
                f"Wrap: <{mod}> \u2026 </{mod}>", ("wrap", mod)
            )
        for label, names in SPECIAL_KEYS:
            for name in sorted(names):
                self.special_combo.addItem(f"Key: {name}", ("key", name))

    def _insert_special(self) -> None:
        data = self.special_combo.currentData()
        if data is None:
            return
        kind, value = data
        if kind == "space":
            self.text_edit.insert(" ")
        elif kind == "key":
            self.text_edit.insert(f"<{value}>")
        elif kind == "wrap":
            close = f"</{value}>"
            self.text_edit.insert(f"<{value}>{close}")
            self.text_edit.setCursorPosition(
                self.text_edit.cursorPosition() - len(close)
            )
        self.special_combo.setCurrentIndex(0)
        self.text_edit.setFocus()

    def add_to_queue(self) -> None:
        text = self.text_edit.text()
        if not text:
            self._status("Type the text to send first (e.g. ing).")
            return

        chord = self._selected_chord()
        if chord is None:
            self._status("Click the keys for the chord first.")
            return

        chord_id = format_chord(chord)
        editing = self._edit_text is not None

        used = find_by_chord(self.config, chord)
        queue_used = []
        for item in self.inbox.items():
            if editing and item.text == self._edit_text:
                continue
            if item.chord_id:
                try:
                    if parse_chord_spec(item.chord_id) == chord:
                        queue_used.append(item)
                except ValueError:
                    continue

        if editing:
            text_collision = None
            if text != self._edit_text:
                other = self.inbox.find(text)
                if other is not None:
                    text_collision = other.text

            problems = []
            if used:
                problems.append("that chord is already on the device")
            if queue_used:
                problems.append("that chord is already in the queue")
            if text_collision is not None:
                problems.append(
                    f"the output \u201c{display_text(text)}\u201d is already in the queue"
                )
            if problems:
                message = " and ".join(problems)
                message = message[0].upper() + message[1:] + "."
                if not self._confirm_overwrite(
                    message + "\nOverwrite the queue item anyway?"
                ):
                    return

            if text_collision is not None:
                self.inbox.remove(text_collision)
            self.inbox.update(
                self._edit_text, new_text=text, chord_id=chord_id, override=bool(used)
            )
            self.text_edit.clear()
            self.keyboard.clear()
            self._reset_edit_mode()
            self.queue_changed.emit()
            self._status(f"Saved \u201c{display_text(text)}\u201d ({chord_id}).")
            return

        if used:
            if not self._confirm_reassign(used, text):
                return
            self.inbox.add(text, chord_id=chord_id, override=True)
            self.text_edit.clear()
            self.keyboard.clear()
            self.queue_changed.emit()
            self._status(
                f"Reassigned \u201c{display_text(text)}\u201d to the export queue ({chord_id})."
            )
            return
        if queue_used:
            who = ", ".join(
                f"\u201c{display_text(item.text)}\u201d" for item in queue_used
            )
            self._status(f"That chord is already in the queue for: {who}.")
            return

        self.inbox.add(text, chord_id=chord_id)
        self.text_edit.clear()
        self.keyboard.clear()
        self.queue_changed.emit()
        self._status(f"Added \u201c{display_text(text)}\u201d to the export queue ({chord_id}).")

    def _confirm_reassign(self, used_bindings, new_text: str) -> bool:
        current = ", ".join(display_action(b.raw_action) for b in used_bindings)
        box = QMessageBox(self)
        box.setWindowTitle("Chord already on device")
        box.setText(f"This chord currently types: {current}.")
        box.setInformativeText(
            f"Reassign it to \u201c{display_text(new_text)}\u201d? The existing "
            "binding will be replaced when you export."
        )
        box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        box.button(QMessageBox.Yes).setText("Reassign")
        return box.exec() == QMessageBox.Yes

    def _status(self, message: str) -> None:
        self.status.setText(message)
