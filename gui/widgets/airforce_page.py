# gui/widgets/airforce_page.py
"""
Airforce Page - Image generation interface for the Airforce API.
Provides controls for prompt, model, size, seed and displays generated images.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QEvent
from PyQt6.QtGui import QCursor

import os

from gui.widgets.image_gen_common import (
    ImageDisplay, INPUT_STYLE, BTN_GENERATE, BTN_CANCEL,
    BTN_DROPDOWN, make_dropdown,
)
from core.services.airforce_service import AirforceService
from core.utils import open_file


class AirforcePage(QWidget):
    """Airforce AI image generation page with controls and image display."""

    status_updated = pyqtSignal(str)

    MODELS = ["grok-imagine", "imagen-4"]
    SIZES = ["1024x1024", "1344x768", "768x1344"]
    DEFAULT_MODEL = "grok-imagine"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_SEED = -1

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

        self.service = AirforceService()
        self.service.image_generated.connect(self._on_image_generated)
        self.service.error_occurred.connect(self._on_error)
        self.service.status_updated.connect(self.status_updated.emit)

        self._build_ui()
        self._load_from_config()

    # ------------------------------------------------------------------ UI

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
        self.generate_btn.setStyleSheet(BTN_GENERATE)
        self.generate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.generate_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        cl.addWidget(self.generate_btn)

        self.positive_input = QLineEdit()
        self.positive_input.setPlaceholderText("Positive Prompt...")
        self.positive_input.setStyleSheet(INPUT_STYLE)
        self.positive_input.returnPressed.connect(self._on_generate_clicked)
        cl.addWidget(self.positive_input, stretch=2)

        self.negative_input = QLineEdit()
        self.negative_input.setPlaceholderText("Negative Prompt...")
        self.negative_input.setStyleSheet(INPUT_STYLE)
        self.negative_input.returnPressed.connect(self._on_generate_clicked)
        cl.addWidget(self.negative_input, stretch=1)

        self.model_btn = QPushButton(self.current_model)
        self.model_btn.setStyleSheet(BTN_DROPDOWN)
        self.model_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.model_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.model_btn.setMinimumWidth(100)
        self.model_btn.installEventFilter(self)
        cl.addWidget(self.model_btn)

        self.size_btn = QPushButton(self.current_size)
        self.size_btn.setStyleSheet(BTN_DROPDOWN)
        self.size_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.size_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.size_btn.setMinimumWidth(90)
        self.size_btn.installEventFilter(self)
        cl.addWidget(self.size_btn)

        self.seed_input = QLineEdit(str(self.DEFAULT_SEED))
        self.seed_input.setStyleSheet(INPUT_STYLE)
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

        # --- Dropdowns ---
        self.model_dropdown = make_dropdown(
            self, self.MODELS, self._on_model_selected, self
        )
        self.size_dropdown = make_dropdown(
            self, self.SIZES, self._on_size_selected, self
        )

    # -------------------------------------------------------------- Dropdowns

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

        self._set_generating(True)
        self._save_to_config()
        self.service.generate_image(
            prompt=prompt,
            negative_prompt=self.negative_input.text().strip(),
            model=self.current_model,
            size=self.current_size,
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
            self.generate_btn.setStyleSheet(BTN_CANCEL)
        else:
            self.generate_btn.setText("Generate")
            self.generate_btn.setStyleSheet(BTN_GENERATE)

    def hideEvent(self, event):
        """Close dropdowns when page is hidden (tab switch)."""
        self._hide_dropdown()
        super().hideEvent(event)

    def _on_image_clicked(self):
        """Open the current image with the system default viewer."""
        if self._current_image_path and os.path.isfile(self._current_image_path):
            open_file(self._current_image_path)
        else:
            self.status_updated.emit("Image file not found on disk.")

    # ------------------------------------------------------------- Config

    def _save_to_config(self):
        """Persist current Airforce settings to config."""
        if not self.config_manager:
            return
        self.config_manager.airforce_positive_prompt = self.positive_input.text()
        self.config_manager.airforce_negative_prompt = self.negative_input.text()
        self.config_manager.airforce_model = self.current_model
        self.config_manager.airforce_size = self.current_size
        try:
            self.config_manager.airforce_seed = int(self.seed_input.text())
        except ValueError:
            self.config_manager.airforce_seed = self.DEFAULT_SEED
        self.config_manager.airforce_last_image = self._current_image_path
        self.config_manager.save()

    def _load_from_config(self):
        """Load persisted Airforce settings from config."""
        if not self.config_manager:
            return

        self.positive_input.setText(
            getattr(self.config_manager, 'airforce_positive_prompt', ''))
        self.negative_input.setText(
            getattr(self.config_manager, 'airforce_negative_prompt', ''))

        model = getattr(self.config_manager, 'airforce_model', self.DEFAULT_MODEL)
        if model in self.MODELS:
            self.current_model = model
            self.model_btn.setText(model)

        size = getattr(self.config_manager, 'airforce_size', self.DEFAULT_SIZE)
        if size in self.SIZES:
            self.current_size = size
            self.size_btn.setText(size)

        seed = getattr(self.config_manager, 'airforce_seed', self.DEFAULT_SEED)
        self.seed_input.setText(str(seed))

        last_image = getattr(self.config_manager, 'airforce_last_image', '')
        if last_image and os.path.isfile(last_image):
            self._current_image_path = last_image
            self.image_display.set_image(last_image)