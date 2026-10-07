"""Export Queue tab: queue letter pairings and export them into a .cfg."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import cfg_io
from ..inbox import Inbox
from ..lookup import find_by_chord, find_by_text
from ..model import display_action, display_text, format_chord, parse_chord_spec


class InboxTab(QWidget):
    edit_requested = Signal(str)

    def __init__(self, inbox: Inbox, config, parent=None):
        super().__init__(parent)
        self.inbox = inbox
        self.config = config
        self.base_cfg: bytes | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Add a chord (letter pairing) you want on your Twiddler:")
        )

        row = QHBoxLayout()
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("e.g. or, ing, st")
        self.text_edit.returnPressed.connect(self.add)
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add)
        row.addWidget(self.text_edit, 1)
        row.addWidget(self.add_btn)
        layout.addLayout(row)

        chord_row = QHBoxLayout()
        chord_row.addWidget(QLabel("Chord (optional):"))
        self.chord_edit = QLineEdit()
        self.chord_edit.setPlaceholderText("e.g. F2M 3R 4R  (or T12 F2M 3R)")
        self.chord_edit.returnPressed.connect(self.add)
        chord_row.addWidget(self.chord_edit, 1)
        layout.addLayout(chord_row)

        self.flag_label = QLabel("")
        self.flag_label.setWordWrap(True)
        layout.addWidget(self.flag_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Output", "Chord", "Status", "", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table, 1)

        queue_btn_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear all on device")
        self.clear_btn.clicked.connect(self.clear_on_device)
        self.export_cfg_btn = QPushButton("Export .cfg\u2026")
        self.export_cfg_btn.clicked.connect(self.export_cfg)
        queue_btn_row.addWidget(self.clear_btn)
        queue_btn_row.addWidget(self.export_cfg_btn)
        queue_btn_row.addStretch(1)
        layout.addLayout(queue_btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.path_label = QLabel(f"Saved to: {self.inbox.path}")
        layout.addWidget(self.path_label)

        self.text_edit.textChanged.connect(self._clear_flag)
        self.chord_edit.textChanged.connect(self._clear_flag)
        self.refresh()

    def set_config(self, config) -> None:
        self.config = config
        self.refresh()

    def set_base_cfg(self, base_cfg: bytes | None) -> None:
        self.base_cfg = base_cfg

    def _on_device(self, text: str):
        matches = find_by_text(self.config, text)
        return [b for b in matches if b.action.typed_text.lower() == text.lower()]

    def _chord_matches(self, chord_id: str, chord) -> bool:
        try:
            return parse_chord_spec(chord_id) == chord
        except ValueError:
            return False

    def _clear_flag(self, *args) -> None:
        self.flag_label.setText("")

    def _status_for(self, item) -> str:
        if self._on_device(item.text):
            return "on device"
        if item.status == "exported":
            return "exported"
        return "pending"

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for item in self.inbox.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            out_item = QTableWidgetItem(display_text(item.text))
            out_item.setData(Qt.UserRole, item.text)
            self.table.setItem(row, 0, out_item)
            self.table.setItem(row, 1, QTableWidgetItem(item.chord_id or ""))
            self.table.setItem(row, 2, QTableWidgetItem(self._status_for(item)))

            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(
                lambda checked=False, t=item.text: self._remove_text(t)
            )
            self.table.setCellWidget(row, 3, remove_btn)

            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(
                lambda checked=False, t=item.text: self._edit_text(t)
            )
            self.table.setCellWidget(row, 4, edit_btn)

    def add(self) -> None:
        text = self.text_edit.text()
        if not text:
            return

        on_device = self._on_device(text)
        if on_device:
            chords = "\n".join(f"  {format_chord(b.chord)}" for b in on_device)
            self.flag_label.setText(
                f"\u26a0 \u201c{display_text(text)}\u201d is already on your device:\n{chords}"
            )
            return

        existing = self.inbox.find(text)
        if existing is not None:
            self.flag_label.setText(
                f"\u26a0 \u201c{display_text(text)}\u201d is already in your export queue "
                f"({existing.status})."
            )
            return

        spec = self.chord_edit.text().strip()
        chord_id = None
        if spec:
            try:
                chord = parse_chord_spec(spec)
            except ValueError as exc:
                self.flag_label.setText(f"\u26a0 Invalid chord: {exc}")
                return

            used = find_by_chord(self.config, chord)
            if used:
                if not self._confirm_reassign(used, text):
                    return
                self.inbox.add(text, chord_id=format_chord(chord), override=True)
                self.text_edit.clear()
                self.chord_edit.clear()
                self._clear_flag()
                self.refresh()
                return

            inbox_used = [
                item
                for item in self.inbox.items()
                if item.chord_id and self._chord_matches(item.chord_id, chord)
            ]
            if inbox_used:
                who = ", ".join(f"\u201c{item.text}\u201d" for item in inbox_used)
                self.flag_label.setText(
                    f"\u26a0 That chord is already defined in your queue for: {who}"
                )
                return

            chord_id = format_chord(chord)

        self.inbox.add(text, chord_id=chord_id)
        self.text_edit.clear()
        self.chord_edit.clear()
        self._clear_flag()
        self.refresh()

    def _remove_text(self, text: str) -> None:
        item = self.inbox.find(text)
        if item is None:
            return
        if item.status == "exported" and not self._confirm_remove_exported(text):
            return
        self.inbox.remove(text)
        self.refresh()

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

    def _confirm_remove_exported(self, text: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("Already exported")
        box.setText(f"\u201c{display_text(text)}\u201d was already exported.")
        box.setInformativeText(
            "Removing it from the queue does not remove its chord from the "
            "exported .cfg file. Remove anyway?"
        )
        box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        box.button(QMessageBox.Yes).setText("Remove anyway")
        return box.exec() == QMessageBox.Yes

    def _edit_text(self, text: str) -> None:
        self.edit_requested.emit(text)

    def clear_on_device(self) -> None:
        targets = [item.text for item in self.inbox.items() if self._on_device(item.text)]
        if not targets:
            self.status_label.setText(
                "Nothing to clear \u2014 no queue items are currently on the device."
            )
            return

        box = QMessageBox(self)
        box.setWindowTitle("Clear on device")
        box.setText(
            f"Remove {len(targets)} queue item(s) that are already on your device?"
        )
        box.setInformativeText(
            "This only removes them from the export queue; nothing is changed "
            "on the Twiddler."
        )
        box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        box.button(QMessageBox.Yes).setText("Clear")
        if box.exec() != QMessageBox.Yes:
            return

        for text in targets:
            self.inbox.remove(text)
        self.refresh()
        self.status_label.setText(
            "Removed from queue (already on device): "
            + ", ".join(display_text(t) for t in targets)
        )

    def export_cfg(self) -> None:
        if self.base_cfg is not None:
            base = self.base_cfg
        else:
            base_path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose your current .cfg file",
                "",
                "CFG files (*.cfg);;All files (*)",
            )
            if not base_path:
                return
            try:
                base = Path(base_path).read_bytes()
            except OSError as exc:
                QMessageBox.warning(self, "Read failed", str(exc))
                return
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export merged .cfg",
            "twiddler_merged.cfg",
            "CFG files (*.cfg);;All files (*)",
        )
        if not out_path:
            return
        self.status_label.setText(self._merge_base(base, out_path))

    def export_cfg_to(self, base_path, out_path) -> str:
        """Merge pending queue items into a base .cfg and write the result."""
        try:
            base = Path(base_path).read_bytes()
        except OSError as exc:
            return f"Could not read base .cfg: {exc}"
        return self._merge_base(base, out_path)

    def _merge_base(self, base: bytes, out_path: str) -> str:
        try:
            base_cfg = cfg_io.parse_cfg(base)
        except ValueError as exc:
            return f"Could not parse base .cfg: {exc}"

        used = {r.combo for r in base_cfg.records}
        additions = []
        replacements = []
        skipped = []
        for item in self.inbox.pending():
            if not item.chord_id:
                skipped.append((item.text, "no chord defined"))
                continue
            try:
                chord = parse_chord_spec(item.chord_id)
            except ValueError as exc:
                skipped.append((item.text, str(exc)))
                continue
            combo = cfg_io.chord_to_combo(chord)
            if item.override:
                if combo not in used:
                    skipped.append((item.text, "marked as reassign but chord not in .cfg"))
                    continue
                replacements.append((chord, item.text))
            else:
                if combo in used:
                    skipped.append((item.text, "chord already in .cfg"))
                    continue
                used.add(combo)
                additions.append((chord, item.text))

        if not additions and not replacements:
            msg = "Nothing to export: no pending queue items with an unused chord."
            if skipped:
                msg += "\nSkipped: " + "; ".join(f"{t} ({r})" for t, r in skipped)
            return msg

        try:
            out = base
            if replacements:
                out = cfg_io.replace_macros(out, replacements)
            if additions:
                out = cfg_io.add_macros(out, additions)
            Path(out_path).write_bytes(out)
        except (OSError, ValueError) as exc:
            return f"Export failed: {exc}"

        for _, text in additions + replacements:
            self.inbox.mark_exported(text)
        self.refresh()

        parts = []
        if additions:
            parts.append(f"{len(additions)} new chord(s)")
        if replacements:
            parts.append(f"{len(replacements)} reassigned chord(s)")
        summary = f"Exported {' and '.join(parts)} to {out_path} (marked as exported)."
        if skipped:
            summary += "\nSkipped: " + "; ".join(f"{t} ({r})" for t, r in skipped)
        return summary
