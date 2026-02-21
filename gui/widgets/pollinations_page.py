# gui/widgets/pollinations_page.py
"""
Pollinations Page - Image generation interface for the Pollinations AI API.
Provides controls for prompt, model, size, seed and displays generated images.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QEvent
from PyQt6.QtGui import QCursor, QPixmap

import os

from core.services.pollinations_service import PollinationsService
from core.utils import reveal_file_in_explorer


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


class PollinationsPage(QWidget):
    """Pollinations AI image generation page with controls and image display."""

    status_updated = pyqtSignal(str)

    MODELS = ["flux", "zimage", "klein", "klein-large", "gptimage"]
    SIZES = ["1024x1024", "1344x768", "768x1344"]
    DEFAULT_MODEL = "zimage"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_SEED = -1

    _INPUT_STYLE = (
        "QLineEdit {"
        "  background-color: #1e1e1e; color: #eee;"
        "  border: 1px solid #333; border-radius: 3px;"
        "  font-size: 12px; padding: 6px;"
        "}"
        "QLineEdit:disabled { color: #666; }"
    )

    _BTN_GENERATE = (
        "QPushButton {"
        "  background-color: #1E88E5; color: #fff; font-weight: bold;"
        "  border: 1px solid #1E88E5; border-radius: 3px;"
        "  font-size: 12px; padding: 6px 12px;"
        "}"
        "QPushButton:hover { background-color: #2A9BF8; border-color: #2A9BF8; }"
        "QPushButton:pressed { background-color: #1966C2; border-color: #1966C2; }"
    )

    _BTN_CANCEL = (
        "QPushButton {"
        "  background-color: #F44336; color: #fff; font-weight: bold;"
        "  border: 1px solid #F44336; border-radius: 3px;"
        "  font-size: 12px; padding: 6px 12px;"
        "}"
        "QPushButton:hover { background-color: #EF5350; border-color: #EF5350; }"
        "QPushButton:pressed { background-color: #D32F2F; border-color: #D32F2F; }"
    )

    _BTN_DROPDOWN = (
        "QPushButton {"
        "  background-color: #1e1e1e; color: #eee;"
        "  border: 1px solid #333; border-radius: 3px;"
        "  font-size: 12px; padding: 6px 8px;"
        "}"
        "QPushButton:hover { background-color: #2a2a2a; border-color: #555; }"
        "QPushButton:disabled { color: #666; }"
    )

    _DROPDOWN_OPTION = (
        "QPushButton {"
        "  background-color: transparent; color: #eee; border: none;"
        "  text-align: left; padding: 6px 12px; font-size: 12px;"
        "}"
        "QPushButton:hover { background-color: #2a2a2a; }"
    )

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_model = self.DEFAULT_MODEL
        self.current_size = self.DEFAULT_SIZE
        self._is_generating = False
        self._current_image_path = ""

        self.active_dropdown = None
        self.hide_timer = QTimer()
        self.hide_timer.setInterval(250)
        self.hide_timer.timeout.connect(self._hide_dropdown)

        self.service = PollinationsService()
        self.service.image_generated.connect(self._on_image_generated)
        self.service.error_occurred.connect(self._on_error)
        self.service.status_updated.connect(self.status_updated.emit)

        self._build_ui()
        self._load_from_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Controls bar ---
        controls = QWidget()
        controls.setStyleSheet("background-color: #121212;")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(6)

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setStyleSheet(self._BTN_GENERATE)
        self.generate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.generate_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        cl.addWidget(self.generate_btn)

        self.positive_input = QLineEdit()
        self.positive_input.setPlaceholderText("Positive Prompt...")
        self.positive_input.setStyleSheet(self._INPUT_STYLE)
        self.positive_input.returnPressed.connect(self._on_generate_clicked)
        cl.addWidget(self.positive_input, stretch=2)

        self.negative_input = QLineEdit()
        self.negative_input.setPlaceholderText("Negative Prompt...")
        self.negative_input.setStyleSheet(self._INPUT_STYLE)
        self.negative_input.returnPressed.connect(self._on_generate_clicked)
        cl.addWidget(self.negative_input, stretch=1)

        self.model_btn = QPushButton(self.current_model)
        self.model_btn.setStyleSheet(self._BTN_DROPDOWN)
        self.model_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.model_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.model_btn.setMinimumWidth(90)
        self.model_btn.installEventFilter(self)
        cl.addWidget(self.model_btn)

        self.size_btn = QPushButton(self.current_size)
        self.size_btn.setStyleSheet(self._BTN_DROPDOWN)
        self.size_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.size_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.size_btn.setMinimumWidth(90)
        self.size_btn.installEventFilter(self)
        cl.addWidget(self.size_btn)

        self.seed_input = QLineEdit(str(self.DEFAULT_SEED))
        self.seed_input.setStyleSheet(self._INPUT_STYLE)
        self.seed_input.setFixedWidth(64)
        self.seed_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seed_input.setToolTip("Seed (-1 for random)")
        self.seed_input.returnPressed.connect(self._on_generate_clicked)
        cl.addWidget(self.seed_input)

        layout.addWidget(controls)

        # --- Image display ---
        self.image_display = ImageDisplay()
        self.image_display.clicked.connect(self._on_image_clicked)
        layout.addWidget(self.image_display, 1)

        self._create_dropdowns()

    def _create_dropdowns(self):
        self.model_dropdown = self._make_dropdown(self.MODELS, self._on_model_selected)
        self.size_dropdown = self._make_dropdown(self.SIZES, self._on_size_selected)

    def _make_dropdown(self, options: list, callback) -> QWidget:
        dd = QWidget(self.window() or None)
        dd.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        dd.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        dd.setStyleSheet(
            "QWidget { background-color: #1e1e1e; border: 1px solid #333; border-radius: 3px; }"
        )
        lo = QVBoxLayout(dd)
        lo.setContentsMargins(2, 2, 2, 2)
        lo.setSpacing(1)

        for opt in options:
            btn = QPushButton(opt)
            btn.setStyleSheet(self._DROPDOWN_OPTION)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, o=opt: callback(o))
            lo.addWidget(btn)

        dd.adjustSize()
        dd.hide()
        dd.installEventFilter(self)
        return dd

    # ---------------------------------------------------------------- Dropdowns

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.Enter:
            if obj == self.model_btn:
                self._show_dropdown(self.model_dropdown, self.model_btn)
            elif obj == self.size_btn:
                self._show_dropdown(self.size_dropdown, self.size_btn)
            elif obj in (self.model_dropdown, self.size_dropdown):
                self.hide_timer.stop()
        elif et == QEvent.Type.Leave:
            if obj in (self.model_btn, self.size_btn,
                       self.model_dropdown, self.size_dropdown):
                self.hide_timer.start()
        return super().eventFilter(obj, event)

    def _show_dropdown(self, dropdown, button):
        if self._is_generating:
            return
        self.hide_timer.stop()
        if self.active_dropdown and self.active_dropdown is not dropdown:
            self.active_dropdown.hide()
        if self.active_dropdown is dropdown:
            return
        self.active_dropdown = dropdown
        pos = button.mapToGlobal(button.rect().bottomLeft())
        dropdown.move(pos.x(), pos.y() + 2)
        dropdown.show()
        dropdown.raise_()

    def _hide_dropdown(self):
        if self.active_dropdown:
            self.active_dropdown.hide()
            self.active_dropdown = None

    def _on_model_selected(self, model: str):
        self.current_model = model
        self.model_btn.setText(model)
        self._hide_dropdown()
        self._save_to_config()

    def _on_size_selected(self, size: str):
        self.current_size = size
        self.size_btn.setText(size)
        self._hide_dropdown()
        self._save_to_config()

    # ------------------------------------------------------------ Generation

    def _on_generate_clicked(self):
        if self._is_generating:
            self.service.cancel_generation()
            self._set_generating(False)
            self.status_updated.emit("Generation cancelled.")
            return

        prompt = self.positive_input.text().strip()
        if not prompt:
            self.status_updated.emit("Error: Positive prompt cannot be empty.")
            return

        try:
            seed = int(self.seed_input.text().strip())
        except ValueError:
            seed = -1

        w, h = self.current_size.split("x")
        self._set_generating(True)
        self._save_to_config()
        self.service.generate_image(
            prompt=prompt,
            negative_prompt=self.negative_input.text().strip(),
            model=self.current_model,
            width=int(w),
            height=int(h),
            seed=seed,
        )

    def _on_image_generated(self, filepath: str):
        self._set_generating(False)
        self._current_image_path = filepath
        self.image_display.set_image(filepath)
        self._save_to_config()

    def _on_error(self, _error_msg: str):
        self._set_generating(False)

    def _set_generating(self, state: bool):
        self._is_generating = state
        self.positive_input.setEnabled(not state)
        self.negative_input.setEnabled(not state)
        self.model_btn.setEnabled(not state)
        self.size_btn.setEnabled(not state)
        self.seed_input.setEnabled(not state)

        if state:
            self._hide_dropdown()
            self.generate_btn.setText("Cancel")
            self.generate_btn.setStyleSheet(self._BTN_CANCEL)
        else:
            self.generate_btn.setText("Generate")
            self.generate_btn.setStyleSheet(self._BTN_GENERATE)

    def hideEvent(self, event):
        """Close dropdowns when page is hidden (tab switch)."""
        self._hide_dropdown()
        super().hideEvent(event)

    def _on_image_clicked(self):
        """Open file explorer and select the current image."""
        if self._current_image_path and os.path.isfile(self._current_image_path):
            reveal_file_in_explorer(self._current_image_path)
        else:
            self.status_updated.emit("Image file not found on disk.")

    def _save_to_config(self):
        """Persist current Pollinations settings to config."""
        if not self.config_manager:
            return
        self.config_manager.pollinations_positive_prompt = self.positive_input.text()
        self.config_manager.pollinations_negative_prompt = self.negative_input.text()
        self.config_manager.pollinations_model = self.current_model
        self.config_manager.pollinations_size = self.current_size
        try:
            self.config_manager.pollinations_seed = int(self.seed_input.text())
        except ValueError:
            self.config_manager.pollinations_seed = self.DEFAULT_SEED
        self.config_manager.pollinations_last_image = self._current_image_path
        self.config_manager.save()

    def _load_from_config(self):
        """Load persisted Pollinations settings from config."""
        if not self.config_manager:
            return

        self.positive_input.setText(
            getattr(self.config_manager, 'pollinations_positive_prompt', ''))
        self.negative_input.setText(
            getattr(self.config_manager, 'pollinations_negative_prompt', ''))

        model = getattr(self.config_manager, 'pollinations_model', self.DEFAULT_MODEL)
        if model in self.MODELS:
            self.current_model = model
            self.model_btn.setText(model)

        size = getattr(self.config_manager, 'pollinations_size', self.DEFAULT_SIZE)
        if size in self.SIZES:
            self.current_size = size
            self.size_btn.setText(size)

        seed = getattr(self.config_manager, 'pollinations_seed', self.DEFAULT_SEED)
        self.seed_input.setText(str(seed))

        last_image = getattr(self.config_manager, 'pollinations_last_image', '')
        if last_image and os.path.isfile(last_image):
            self._current_image_path = last_image
            self.image_display.set_image(last_image)