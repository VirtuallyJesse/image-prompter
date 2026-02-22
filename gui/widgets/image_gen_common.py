# gui/widgets/image_gen_common.py
"""
Shared components for image generation pages.
Provides ImageDisplay widget, UI style constants, and dropdown factory.
"""

from collections import OrderedDict

from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QCursor, QPixmap, QImageReader


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
    """Custom label that displays an image fully contained, never cropped.

    When *gallery_mode* is True, images are loaded at a reduced resolution
    (max 400 px on either axis) and kept in a class-level LRU pixmap cache
    so that page navigation is near-instant.  Resize events are also
    throttled to avoid redundant scaling during window drag.
    """

    clicked = pyqtSignal()
    right_clicked = pyqtSignal()

    # Class-level LRU pixmap cache shared by all gallery-mode instances
    _gallery_cache: OrderedDict = OrderedDict()
    _GALLERY_CACHE_MAX = 72        # ~6 pages of 12 items
    _GALLERY_LOAD_SIZE = 400       # max px on either axis when loading

    def __init__(self, parent=None, gallery_mode=False):
        super().__init__(parent)
        self._pixmap = None
        self._filepath = ""
        self._gallery_mode = gallery_mode
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(64, 64)
        self.setStyleSheet("background-color: #121212; border: none;")

        if gallery_mode:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.setInterval(50)
            self._resize_timer.timeout.connect(self._update_display)

    # ── public API ──────────────────────────────────────────────────────

    def set_image(self, filepath: str):
        """Load and display an image from *filepath*."""
        if filepath == self._filepath and self._pixmap is not None:
            return                                       # already showing this image
        self._filepath = filepath

        if self._gallery_mode:
            cached = ImageDisplay._gallery_cache.get(filepath)
            if cached is not None:
                self._pixmap = cached
                ImageDisplay._gallery_cache.move_to_end(filepath)
            else:
                self._pixmap = self._load_scaled(filepath, self._GALLERY_LOAD_SIZE)
                if len(ImageDisplay._gallery_cache) >= ImageDisplay._GALLERY_CACHE_MAX:
                    ImageDisplay._gallery_cache.popitem(last=False)
                ImageDisplay._gallery_cache[filepath] = self._pixmap
        else:
            self._pixmap = QPixmap(filepath)

        self._update_display()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def clear_image(self):
        self._pixmap = None
        self._filepath = ""
        self.clear()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # ── events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._pixmap:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
            elif event.button() == Qt.MouseButton.RightButton:
                self.right_clicked.emit()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            if self._gallery_mode:
                self._resize_timer.start()               # throttled
            else:
                self._update_display()

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _load_scaled(filepath: str, max_dim: int) -> QPixmap:
        """Load an image at reduced resolution via QImageReader.

        Leverages JPEG's built-in DCT scaling so the decoder never
        decompresses full-resolution pixel data.
        """
        reader = QImageReader(filepath)
        reader.setAutoTransform(True)
        orig_size = reader.size()
        if orig_size.isValid() and (orig_size.width() > max_dim or orig_size.height() > max_dim):
            scaled_size = orig_size.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(scaled_size)
        image = reader.read()
        if not image.isNull():
            return QPixmap.fromImage(image)
        return QPixmap(filepath)                         # fallback

    def _update_display(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)


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