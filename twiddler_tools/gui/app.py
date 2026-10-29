"""Application entry point and main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from ..inbox import Inbox
from ..model import Config
from ..settings import load_gui_scale, load_last_app, load_last_config, save_last_app
from .chord_editor_tab import ChordEditorTab
from .config_tab import ConfigTab
from .inbox_tab import InboxTab
from .lookup_tab import LookupTab


class MainWindow(QMainWindow):
    def __init__(self, config: Config, inbox: Inbox, parent=None):
        super().__init__(parent)
        self.config = config
        self.inbox = inbox
        self.setWindowTitle("Twiddler 4 Tools")

        self.tabs = QTabWidget()
        self.inbox_tab = InboxTab(inbox, config)
        self.chord_editor_tab = ChordEditorTab(config, inbox)
        self.lookup_tab = LookupTab(config, inbox)
        self.config_tab = ConfigTab(config, inbox)
        self.tabs.addTab(self.inbox_tab, "Export Queue")
        self.tabs.addTab(self.chord_editor_tab, "Chord Editor")
        self.tabs.addTab(self.lookup_tab, "Chord Lookup")
        self.tabs.addTab(self.config_tab, "Config")
        self._app_tabs = {
            "Export Queue": self.inbox_tab,
            "Chord Editor": self.chord_editor_tab,
            "Chord Lookup": self.lookup_tab,
            "Config": self.config_tab,
        }
        self.tabs.setCurrentWidget(self._app_tabs.get(load_last_app(), self.lookup_tab))
        self.tabs.currentChanged.connect(self._save_current_app)

        self.config_tab.config_changed.connect(self.lookup_tab.refresh_config)
        self.config_tab.config_changed.connect(self.inbox_tab.set_config)
        self.config_tab.config_changed.connect(self.chord_editor_tab.set_config)
        self.config_tab.base_cfg_changed.connect(self.inbox_tab.set_base_cfg)
        self.chord_editor_tab.queue_changed.connect(self.inbox_tab.refresh)
        self.inbox_tab.edit_requested.connect(self._open_chord_editor)
        self.lookup_tab.add_output_requested.connect(self._open_chord_editor_with_chord)
        self.config_tab.scale_changed.connect(self._apply_scale)
        self.config_tab.scale_changed.connect(self._size_to_fit)
        self.setCentralWidget(self.tabs)

        self._apply_scale(load_gui_scale())
        self._size_to_fit()

    def _save_current_app(self, index: int) -> None:
        save_last_app(self.tabs.tabText(index))

    def _size_to_fit(self) -> None:
        """Size the window to show the full keymap at the current scale.

        This only sets the *initial* size; the user can still resize the
        window smaller afterwards (the keymap then clips at the bottom).
        """
        # The keymap scale change invalidates the editor layout, so make sure
        # its size hint is recomputed before asking the tab widget for one.
        self.chord_editor_tab.layout().invalidate()
        self.chord_editor_tab.layout().activate()
        hint = self.tabs.sizeHint()
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(hint.width(), available.width())
            height = min(hint.height(), available.height())
        else:
            width, height = hint.width(), hint.height()
        self.resize(width, height)

    def _apply_scale(self, factor: float) -> None:
        self.chord_editor_tab.set_scale(factor)
        self.lookup_tab.set_scale(factor)

    def _open_chord_editor(self, text: str) -> None:
        self.chord_editor_tab.load_for_edit(text)
        self.tabs.setCurrentWidget(self.chord_editor_tab)

    def _open_chord_editor_with_chord(self, chord) -> None:
        thumbs = frozenset(t.index for t in chord.thumbs)
        fingers = frozenset((k.row, k.col) for k in chord.fingers)
        self.chord_editor_tab.preload_chord(thumbs, fingers)
        self.tabs.setCurrentWidget(self.chord_editor_tab)


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    config, base_cfg = load_last_config()
    window = MainWindow(config, Inbox())
    if base_cfg is not None:
        window.inbox_tab.set_base_cfg(base_cfg)
        window.config_tab.set_base_cfg(base_cfg)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
