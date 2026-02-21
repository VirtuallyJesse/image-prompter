# gui/widgets/image_gen_common.py
"""
Shared components for image generation pages.
Provides ImageDisplay widget, UI style constants, and dropdown factory.
"""

from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QCursor, QPixmap


# ── Shared style constants ─────────────────────────────────────────────────

INPUT_STYLE = (
    "QLineEdit {"
    "  background-color: #1e1e1e; color: #eee;"
    "  border: 1px solid #333; border-radius: 3px;"
    "  font-size: 12px; padding: 6px;"
    "}"
    "QLineEdit:disabled { color: #666; }"
)

BTN_GENERATE = (
    "QPushButton {"
    "  background-color: #1E88E5; color: #fff; font-weight: bold;"
    "  border: 1px solid #1E88E5; border-radius: 3px;"
    "  font-size: 12px; padding: 6px 12px;"
    "}"
    "QPushButton:hover { background-color: #2A9BF8; border-color: #2A9BF8; }"
    "QPushButton:pressed { background-color: #1966C2; border-color: #1966C2; }"
)

BTN_CANCEL = (
    "QPushButton {"
    "  background-color: #F44336; color: #fff; font-weight: bold;"
    "  border: 1px solid #F44336; border-radius: 3px;"
    "  font-size: 12px; padding: 6px 12px;"
    "}"
    "QPushButton:hover { background-color: #EF5350; border-color: #EF5350; }"
    "QPushButton:pressed { background-color: #D32F2F; border-color: #D32F2F; }"
)

BTN_DROPDOWN = (
    "QPushButton {"
    "  background-color: #1e1e1e; color: #eee;"
    "  border: 1px solid #333; border-radius: 3px;"
    "  font-size: 12px; padding: 6px 8px;"
    "}"
    "QPushButton:hover { background-color: #2a2a2a; border-color: #555; }"
    "QPushButton:disabled { color: #666; }"
)

DROPDOWN_OPTION = (
    "QPushButton {"
    "  background-color: transparent; color: #eee; border: none;"
    "  text-align: left; padding: 6px 12px; font-size: 12px;"
    "}"
    "QPushButton:hover { background-color: #2a2a2a; }"
)

DROPDOWN_CONTAINER = (
    "QWidget { background-color: #1e1e1e; border: 1px solid #333; border-radius: 3px; }"
)


# ── Shared widgets ──────────────────────────────────────────────────────────

class ImageDisplay(QLabel):
    """Custom label that displays an image fully contained, never cropped."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(64, 64)
        self.setStyleSheet("background-color: #121212; border: none;")

    def set_image(self, filepath: str):
        """Load and display an image from file path."""
        self._pixmap = QPixmap(filepath)
        self._update_display()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def clear_image(self):
        self._pixmap = None
        self.clear()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _update_display(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()


# ── Shared helpers ──────────────────────────────────────────────────────────

def make_dropdown(parent_widget, options: list, callback, event_filter_obj) -> QWidget:
    """Create a hover-activated dropdown widget with the given options.

    Args:
        parent_widget:    Widget whose window() is used as the dropdown parent.
        options:          List of string labels for the dropdown items.
        callback:         Called with the selected option string on click.
        event_filter_obj: QObject that will receive Enter/Leave events on the dropdown.
    """
    dd = QWidget(parent_widget.window() or None)
    dd.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
    dd.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    dd.setStyleSheet(DROPDOWN_CONTAINER)
    lo = QVBoxLayout(dd)
    lo.setContentsMargins(2, 2, 2, 2)
    lo.setSpacing(1)

    for opt in options:
        btn = QPushButton(opt)
        btn.setStyleSheet(DROPDOWN_OPTION)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.clicked.connect(lambda _, o=opt: callback(o))
        lo.addWidget(btn)

    dd.adjustSize()
    dd.hide()
    dd.installEventFilter(event_filter_obj)
    return dd