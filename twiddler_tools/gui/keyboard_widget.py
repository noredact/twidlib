"""Widget that draws the Twiddler keymap and highlights an active chord.

When made selectable, clicking keys toggles them and emits `selection_changed`;
the current selection can be read back with `selected()`. The whole keymap can
be scaled with `set_scale()` (used by the GUI-size presets).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

ACTIVE_COLOR = QColor("#ff9d2e")
INACTIVE_COLOR = QColor("#3a3f4a")
TEXT_ACTIVE = QColor("#1a1c22")
TEXT_INACTIVE = QColor("#e8e8e8")
LABEL_COLOR = QColor("#8a8f98")

FINGER_ROWS = (1, 2, 3, 4)
MOUSE_ROW = 0
FINGER_COLS = ("L", "M", "R")
THUMB_KEYS = (0, 1, 2, 3, 4)


class KeyboardWidget(QWidget):
    """Renders 12 finger keys and 5 thumb keys, highlighting the active set."""

    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbs: frozenset[int] = frozenset()
        self._fingers: frozenset[tuple[int, str]] = frozenset()
        self._mirror = False
        self._selectable = False
        self._scale = 1.0

    def sizeHint(self) -> QSize:
        """Preferred size; the widget may still shrink below this if the window
        is resized smaller (the bottom of the keymap then clips)."""
        return QSize(int(360 * self._scale), int(600 * self._scale))

    def set_scale(self, factor: float) -> None:
        self._scale = float(factor)
        self.updateGeometry()
        self.update()

    def set_selectable(self, selectable: bool) -> None:
        self._selectable = bool(selectable)
        self.setCursor(Qt.PointingHandCursor if self._selectable else Qt.ArrowCursor)
        self.update()

    def selected(self) -> tuple[frozenset[int], frozenset[tuple[int, str]]]:
        """Return the currently selected (thumbs, fingers)."""
        return self._thumbs, self._fingers

    def set_active_keys(
        self,
        thumbs: frozenset[int] | set[int] = frozenset(),
        fingers: frozenset[tuple[int, str]] | set[tuple[int, str]] = frozenset(),
    ) -> None:
        self._thumbs = frozenset(thumbs)
        self._fingers = frozenset(fingers)
        self.update()

    def clear(self) -> None:
        self.set_active_keys()

    def set_mirror(self, mirror: bool) -> None:
        self._mirror = bool(mirror)
        self.update()

    def row_center_y(self, row: int) -> float:
        """Vertical centre of a finger row in widget coordinates."""
        s = self._scale
        margin = 24 * s
        mcell_h = 34 * s
        y0 = margin + 18 * s + mcell_h + 16 * s
        cell_h = 48 * s
        gap = 10 * s
        return y0 + (row - 1) * (cell_h + gap) + cell_h / 2

    def _display_cols(self) -> tuple[str, str, str]:
        return ("R", "M", "L") if self._mirror else ("L", "M", "R")

    def _geometry(self) -> tuple[dict, dict, dict]:
        """Compute key rects in widget coordinates.

        Returns (mouse_rects, finger_rects, thumb_rects) keyed by logical
        (row, col) / thumb index, where thumb entries are (cx, cy, r).
        """
        s = self._scale
        width = self.width()
        margin = 24 * s
        cell_w = 80 * s
        cell_h = 48 * s
        gap = 10 * s
        grid_w = 3 * cell_w + 2 * gap
        grid_h = 4 * cell_h + 3 * gap
        cols = self._display_cols()

        mcell_w = 72 * s
        mcell_h = 34 * s
        mgap = 8 * s
        mrow_w = 3 * mcell_w + 2 * mgap
        mx0 = (width - mrow_w) / 2
        my0 = margin + 18 * s

        mouse_rects = {}
        for ci, col in enumerate(cols):
            x = mx0 + ci * (mcell_w + mgap)
            mouse_rects[(MOUSE_ROW, col)] = QRectF(x, my0, mcell_w, mcell_h)

        x0 = (width - grid_w) / 2
        y0 = my0 + mcell_h + 16 * s
        finger_rects = {}
        for ri, row in enumerate(FINGER_ROWS):
            for ci, col in enumerate(cols):
                x = x0 + ci * (cell_w + gap)
                y = y0 + ri * (cell_h + gap)
                finger_rects[(row, col)] = QRectF(x, y, cell_w, cell_h)

        rx = 80.0 * s
        ry = 55.0 * s
        thumb_r = 30 * s
        cx = width / 2
        cy = y0 + grid_h + 48 * s + ry
        offsets = {
            0: (0.0, 0.0),
            1: (-1.0, 0.6),
            2: (-0.6, 1.8),
            3: (0.6, 1.8),
            4: (1.0, 0.6),
        }
        thumb_rects = {
            thumb: (cx + ox * rx, cy + oy * ry, thumb_r)
            for thumb, (ox, oy) in offsets.items()
        }
        return mouse_rects, finger_rects, thumb_rects

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        mouse_rects, finger_rects, thumb_rects = self._geometry()

        for (row, col), rect in mouse_rects.items():
            self._draw_key(painter, rect, f"{row}{col}", (row, col) in self._fingers)

        for (row, col), rect in finger_rects.items():
            self._draw_key(painter, rect, f"{row}{col}", (row, col) in self._fingers)

        top_cx, top_cy, top_r = thumb_rects[0]
        painter.setPen(QPen(LABEL_COLOR))
        painter.drawText(
            QRectF(0, top_cy - top_r - 22 * self._scale, width, 16),
            Qt.AlignCenter,
            "Thumb",
        )

        for thumb in THUMB_KEYS:
            cx, cy, r = thumb_rects[thumb]
            self._draw_thumb(painter, cx, cy, r, str(thumb), thumb in self._thumbs)

        painter.end()

    def mousePressEvent(self, event) -> None:
        if not self._selectable:
            super().mousePressEvent(event)
            return
        pos = event.position()
        mouse_rects, finger_rects, thumb_rects = self._geometry()

        for key, rect in {**mouse_rects, **finger_rects}.items():
            if rect.contains(pos):
                self._toggle_finger(key)
                return
        for thumb, (cx, cy, r) in thumb_rects.items():
            if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= r * r:
                self._toggle_thumb(thumb)
                return

    def _toggle_finger(self, key: tuple[int, str]) -> None:
        s = set(self._fingers)
        if key in s:
            s.discard(key)
        else:
            s.add(key)
        self._fingers = frozenset(s)
        self.update()
        self.selection_changed.emit()

    def _toggle_thumb(self, index: int) -> None:
        s = set(self._thumbs)
        if index in s:
            s.discard(index)
        else:
            s.add(index)
        self._thumbs = frozenset(s)
        self.update()
        self.selection_changed.emit()

    def _draw_key(self, painter: QPainter, rect: QRectF, label: str, active: bool) -> None:
        painter.setBrush(ACTIVE_COLOR if active else INACTIVE_COLOR)
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.drawRoundedRect(rect, 8 * self._scale, 8 * self._scale)
        font = QFont()
        font.setBold(True)
        font.setPointSize(max(7, int(11 * self._scale)))
        painter.setFont(font)
        painter.setPen(TEXT_ACTIVE if active else TEXT_INACTIVE)
        painter.drawText(rect, Qt.AlignCenter, label)

    def _draw_thumb(
        self, painter: QPainter, cx: float, cy: float, r: float, label: str, active: bool
    ) -> None:
        painter.setBrush(ACTIVE_COLOR if active else INACTIVE_COLOR)
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        font = QFont()
        font.setBold(True)
        font.setPointSize(max(7, int(11 * self._scale)))
        painter.setFont(font)
        painter.setPen(TEXT_ACTIVE if active else TEXT_INACTIVE)
        painter.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter, label)
