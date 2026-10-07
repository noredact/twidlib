"""Config tab: import the tuner CSV/.cfg export, export JSON, and show help."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import cfg_io, json_io
from ..csv_io import load_csv
from ..settings import load_gui_scale, save_gui_scale, save_last_config

_SIZES = (("Small", 0.6), ("Medium", 0.8), ("Large", 1.0))

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
"""


class ConfigTab(QWidget):
    config_changed = Signal(object)
    base_cfg_changed = Signal(object)  # bytes | None
    scale_changed = Signal(float)

    def __init__(self, config, inbox, parent=None):
        super().__init__(parent)
        self.config = config
        self.inbox = inbox

        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("Import CSV\u2026")
        self.import_btn.clicked.connect(self.import_csv)
        self.import_cfg_btn = QPushButton("Import .cfg\u2026")
        self.import_cfg_btn.clicked.connect(self.import_cfg)
        self.export_btn = QPushButton("Export Tutor JSON\u2026")
        self.export_btn.clicked.connect(self.export_json)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.import_cfg_btn)
        btn_row.addWidget(self.export_btn)
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
        self.config_changed.emit(self.config)
        self.base_cfg_changed.emit(raw)

    def export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export custom-mapping JSON",
            "twiddler_custom.json",
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
