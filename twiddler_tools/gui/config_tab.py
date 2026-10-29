"""Config tab: import the tuner CSV/.cfg export, export JSON, and show help."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import cfg_io, json_io
from ..csv_io import load_csv
from ..settings import (
    DEFAULT_TIMESTAMP_FORMAT,
    load_file_naming,
    load_gui_scale,
    save_file_naming,
    save_gui_scale,
    save_last_config,
)

_SIZES = (("Small", 0.6), ("Medium", 0.8), ("Large", 1.0))

_TIMESTAMP_FORMATS = (
    ("YYYYMMDD", "%Y%m%d"),
    ("YYYY-MM-DD", "%Y-%m-%d"),
    ("YYYY-MM-DD_HHMMSS", "%Y-%m-%d_%H%M%S"),
    ("YYYYMMDD_HHMMSS", "%Y%m%d_%H%M%S"),
    ("YYYYMMDD-HHMMSS", "%Y%m%d-%H%M%S"),
    ("YYYY-MM-DD_HH-MM-SS", "%Y-%m-%d_%H-%M-%S"),
    ("MM-DD-YYYY_HHMMSS", "%m-%d-%Y_%H%M%S"),
    ("HHMMSS", "%H%M%S"),
)

_HELP_HTML = """\
<p><i>Tip: use Ctrl+scroll to zoom this text (Ctrl + / Ctrl - zoom in/out).</i></p>

<h3>Syntax examples (same as the tuner)</h3>
<pre>plain text:        the
shifted symbol:    &lt;RShift&gt;=&lt;/RShift&gt;      -&gt; types =
shifted letters:   &lt;RShift&gt;t&lt;/RShift&gt;he    -&gt; types The
special keys:      &lt;Backspace&gt;, &lt;Enter&gt;, &lt;F1&gt;, &lt;Tab&gt;
modifier wrap:     &lt;LCtrl&gt;c&lt;/LCtrl&gt;        -&gt; Ctrl+C</pre>
<p>Special keys can be inserted from the dropdown in the Chord Editor tab.</p>

<h3>About spaces</h3>
<p>Outputs that contain spaces are shown with <b>[sp]</b> so a space chord can\u2019t
be mistaken for a syntax error: a chord that types a single space shows as
<b>[sp]</b>, and \u201cing \u201d shows as <b>ing[sp]</b>.</p>
<p>The Chord Lookup search box trims spaces, so you can\u2019t find a chord by
typing just a space \u2014 look it up by chord notation (e.g. F2M 3R 4R) or click
the keys on the keymap.</p>

<h3>What this tool does</h3>
<p>This tool was designed to look up chords, facilitate adding new ones, and
facilitate exporting a JSON file for the
<a href="https://tutor.mytwiddler.com/tutor2/index.html">tutor</a>.</p>

<h3>How to use it</h3>
<ol>
<li>Import your current config (.cfg or CSV) downloaded from the tuner.</li>
<li>Look up chords in the <b>Chord Lookup</b> tab.</li>
<li>Add new chords in the <b>Chord Editor</b> tab, or directly in the
<b>Export Queue</b> tab.</li>
<li>Click <b>Export .cfg\u2026</b> (in the Export Queue tab). Settings are
extracted from the .cfg you loaded; otherwise you are prompted for a .cfg file
to add the export queue to before being asked where to save the exported
.cfg.</li>
<li>Sign into the <a href="https://www.mytwiddler.com/tuner/">tuner</a> and
upload the .cfg. This allows the .cfg to be validated by the official
software.</li>
<li>Download the .cfg following the tuner instructions.</li>
</ol>

<h3>CSV to .cfg</h3>
<p><b>CSV to .cfg\u2026</b> rebuilds a .cfg from an edited CSV. It treats the CSV
as the complete config (every row becomes a binding) and takes only the
settings/header from a base .cfg. Use it to turn a tuner-exported CSV that
you\u2019ve edited into a file you can upload to the tuner. Mouse-down/delay/release
sequences are supported when the delay is a positive multiple of 10 ms.</p>
"""


class ConfigTab(QWidget):
    config_changed = Signal(object)
    base_cfg_changed = Signal(object)  # bytes | None
    scale_changed = Signal(float)

    def __init__(self, config, inbox, parent=None):
        super().__init__(parent)
        self.config = config
        self.inbox = inbox
        self.base_cfg: bytes | None = None
        self._kind: str | None = self._kind_from_source(config.source)

        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("Import CSV\u2026")
        self.import_btn.clicked.connect(self.import_csv)
        self.import_cfg_btn = QPushButton("Import .cfg\u2026")
        self.import_cfg_btn.clicked.connect(self.import_cfg)
        self.export_btn = QPushButton("Export Tutor JSON\u2026")
        self.export_btn.clicked.connect(self.export_json)
        self.csv_to_cfg_btn = QPushButton("CSV to .cfg\u2026")
        self.csv_to_cfg_btn.clicked.connect(self.csv_to_cfg)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.import_cfg_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.csv_to_cfg_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Keymap size:"))
        self.size_combo = QComboBox()
        for label, factor in _SIZES:
            self.size_combo.addItem(label, factor)
        current = load_gui_scale()
        for i, (_, factor) in enumerate(_SIZES):
            if abs(factor - current) < 0.01:
                self.size_combo.setCurrentIndex(i)
                break
        self.size_combo.currentIndexChanged.connect(self._size_changed)
        size_row.addWidget(self.size_combo)
        size_row.addWidget(
            QLabel("Shrinks/grows the keymap so the window fits your screen.")
        )
        size_row.addStretch(1)
        layout.addLayout(size_row)

        self.path_label = QLabel(f"Loaded: {self.config.source or '(empty)'}")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Default file name:"))
        self.default_name_edit = QLineEdit()
        self.default_name_edit.setPlaceholderText("e.g. twiddler_custom")
        self.default_name_edit.setToolTip(
            "Base name for exported files. Leave blank to use the per-export "
            "default; the .json/.cfg extension is added automatically."
        )
        name_row.addWidget(self.default_name_edit, 1)
        layout.addLayout(name_row)

        ts_row = QHBoxLayout()
        self.append_ts_cb = QCheckBox("Append timestamp")
        self.timestamp_combo = QComboBox()
        for label, fmt in _TIMESTAMP_FORMATS:
            self.timestamp_combo.addItem(label, fmt)
        ts_row.addWidget(self.append_ts_cb)
        ts_row.addWidget(self.timestamp_combo)
        ts_row.addStretch(1)
        layout.addLayout(ts_row)

        name, append_ts, fmt = load_file_naming()
        self.default_name_edit.setText(name)
        self.append_ts_cb.setChecked(append_ts)
        idx = self.timestamp_combo.findData(fmt)
        self.timestamp_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.timestamp_combo.setEnabled(append_ts)

        self.default_name_edit.textChanged.connect(self._save_file_naming)
        self.append_ts_cb.toggled.connect(self._append_ts_toggled)
        self.append_ts_cb.toggled.connect(lambda checked: self._save_file_naming())
        self.timestamp_combo.currentIndexChanged.connect(
            lambda _: self._save_file_naming()
        )

        self.export_label = QLabel("")
        self.export_label.setWordWrap(True)
        layout.addWidget(self.export_label)

        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(True)
        self.help_browser.setHtml(_HELP_HTML)
        font = self.help_browser.font()
        font.setPointSize(max(11, font.pointSize() + 1))
        self.help_browser.setFont(font)
        layout.addWidget(self.help_browser, 1)

        # QTextBrowser already zooms on Ctrl+scroll; add keyboard shortcuts too.
        self._zoom_in_sc = QShortcut(
            QKeySequence(QKeySequence.StandardKey.ZoomIn),
            self.help_browser,
            activated=self.help_browser.zoomIn,
        )
        self._zoom_out_sc = QShortcut(
            QKeySequence(QKeySequence.StandardKey.ZoomOut),
            self.help_browser,
            activated=self.help_browser.zoomOut,
        )

    def _size_changed(self) -> None:
        factor = self.size_combo.currentData()
        save_gui_scale(factor)
        self.scale_changed.emit(factor)

    def _save_file_naming(self, *args) -> None:
        save_file_naming(
            self.default_name_edit.text().strip(),
            self.append_ts_cb.isChecked(),
            self.timestamp_combo.currentData() or DEFAULT_TIMESTAMP_FORMAT,
        )

    def _append_ts_toggled(self, checked: bool) -> None:
        self.timestamp_combo.setEnabled(checked)

    def _export_filename(self, fallback_stem: str, ext: str) -> str:
        """Build the pre-filled save name from the default-name preferences."""
        base = self.default_name_edit.text().strip() or fallback_stem
        path = Path(base)
        stem = path.stem
        suffix = path.suffix or ext
        if self.append_ts_cb.isChecked():
            fmt = self.timestamp_combo.currentData() or DEFAULT_TIMESTAMP_FORMAT
            stem = f"{stem}_{datetime.now().strftime(fmt)}"
        return f"{stem}{suffix}"

    @staticmethod
    def _kind_from_source(source: str) -> str | None:
        lowered = (source or "").lower()
        if lowered.endswith(".csv"):
            return "csv"
        if lowered.endswith(".cfg"):
            return "cfg"
        return None

    def set_base_cfg(self, base_cfg: bytes | None) -> None:
        """Remember the base .cfg bytes (and kind) loaded at startup."""
        self.base_cfg = base_cfg
        if base_cfg is not None:
            self._kind = "cfg"

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import tuner CSV export", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            self.config = load_csv(path)
        except Exception as exc:  # surface any parse problem to the user
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.path_label.setText(f"Loaded CSV: {path}")
        self.export_label.setText("")
        save_last_config(path, "csv")
        self.base_cfg = None
        self._kind = "csv"
        self.config_changed.emit(self.config)
        self.base_cfg_changed.emit(None)

    def import_cfg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import .cfg config", "", "CFG files (*.cfg);;All files (*)"
        )
        if not path:
            return
        try:
            raw = Path(path).read_bytes()
            parsed = cfg_io.parse_cfg(raw)
            self.config = cfg_io.cfg_to_config(parsed, source=path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.path_label.setText(f"Loaded .cfg: {path} (base for export)")
        self.export_label.setText("")
        save_last_config(path, "cfg")
        self.base_cfg = raw
        self._kind = "cfg"
        self.config_changed.emit(self.config)
        self.base_cfg_changed.emit(raw)

    def export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export custom-mapping JSON",
            self._export_filename("twiddler_custom", ".json"),
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        self.export_label.setText(self.export_json_to(path))

    def export_json_to(self, path) -> str:
        data, skipped = json_io.config_to_custom_json(self.config)
        Path(path).write_text(json_io.render_custom_json(self.config), encoding="utf-8")
        summary = f"Exported {len(data['chords'])} chord(s) to {path}."
        if skipped:
            summary += f"  Skipped {len(skipped)} (system actions or multi-column rows)."
        return summary

    def csv_to_cfg(self) -> None:
        """Rebuild a .cfg from a CSV, reusing settings from a base .cfg."""
        # 1. Pick the CSV: the loaded one if it came from a CSV, else ask.
        if self._kind == "csv" and self.config.source:
            csv_config = self.config
            csv_path = self.config.source
        else:
            csv_path, _ = QFileDialog.getOpenFileName(
                self, "Choose the CSV to convert", "", "CSV files (*.csv);;All files (*)"
            )
            if not csv_path:
                return
            try:
                csv_config = load_csv(csv_path)
            except Exception as exc:  # surface any parse problem to the user
                QMessageBox.warning(self, "Import failed", str(exc))
                return

        # 2. Pick the base .cfg (for settings) if one isn't already loaded.
        if self.base_cfg is not None:
            base = self.base_cfg
        else:
            base_path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose a base .cfg for settings",
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

        # 3. Build the .cfg.
        try:
            out = cfg_io.config_to_cfg(csv_config, base)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Conversion failed",
                "Could not convert this CSV to a .cfg:\n\n"
                + str(exc)
                + "\n\nOnly tuner-exported CSVs are supported.",
            )
            return

        # 4. Save it.
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export .cfg from CSV",
            self._export_filename("twiddler_from_csv", ".cfg"),
            "CFG files (*.cfg);;All files (*)",
        )
        if not out_path:
            return
        try:
            Path(out_path).write_bytes(out)
        except OSError as exc:
            QMessageBox.warning(self, "Write failed", str(exc))
            return
        self.export_label.setText(
            f"Exported {len(csv_config.bindings)} chord(s) from CSV to {out_path}."
        )
