### TASK

Feature Plan: Airforce Page Enhancements - Video Model, Cooldown Timer, and UI Refinements

## Overview

This feature adds video generation support to the Airforce page, implements a 60-second cooldown timer, and refines the UI by removing unused parameters (size and seed).

### Summary of Changes

| Change | Description |
|--------|-------------|
| Remove size dropdown | Airforce only accepts 1024x1024 for image models |
| Remove seed input | Airforce models do not have a controllable seed parameter |
| Add grok-imagine-video model | New video generation model with aspectRatio parameter |
| Add aspectRatio dropdown | Conditional dropdown for video model only (1:1, 2:3, 3:2) |
| Add cooldown timer | 60-second countdown on Generate button after successful generation |
| Video support in gallery | Display videos with hover autoplay in gallery grid |
| Video metadata | Embed metadata in MP4 files using best approach |

---

## TASK DETAILS

Current Airforce page has Top bar: Generate → Positive → Negative → Model → Size → Seed

We're removing both Size and Seed for all Airforce models, as they are not controllable. You still **must** send 1024x1024 for Size in the requests made for all Airforce models. Size is required, it's just not modifiable. Seed should be removed from the airforce payload entirely.

The new video model actually produces videos with audio instead of images. This is a bit of a deviation and new area, but should fit nicely into the project.

Snippet from their website documentation on usage:

```python
import requests
import json

url = "https://api.airforce/v1/images/generations"
headers = {"Authorization": "Bearer YOUR_API_KEY", "Content-Type": "application/json"}
payload = {
  "model": "grok-imagine-video",
  "prompt": "",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json",
  "sse": true,
  "mode": "normal",
  "image_urls": [
    "example.com/image.png"
  ]
}

# SSE handling
with requests.post(url, headers=headers, json=payload, stream=True) as response:
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: ") and line_str != "data: [DONE]" and line_str != "data: : keepalive":
                data = json.loads(line_str[6:])
                print(data)
```

Valid options for aspectRatio are 1:1, 2:3, and 3:2. Size is not adjustable. It also accepts image_urls for image-to-video. We could use this, but we're not integrating it at this time. Just make a note of it / add a comment so that we don't forget it exists for future implementation. 

The top bar should display aspectRatio only when the model is grok-imagine-video. No aspectRatio parameter for the imagen-4 and grok-imagine picture model. aspectRatio should use the dropdown hover behavior. Default 1:1, and add persistence for config.

Ensure the gallery can handle video display and app can handle video downloading + metadata embedding, and video metadata fetching/reading. You may choose any method to enable embedding data as long as there is no sidecar files, even changing from mp4 to any format. (e.g. no json files saved with the video)

Video playback logic: Show play icon overlay for videos, and static first frame. Implement hover detection for autoplay. On mouse enter: Start video playback (loop, audio enabled) On mouse leave: Stop and reset playback, show first frame. Playback never resumes from play position, always starts at beginning on mouse enter. Left click = open file navigation path like images.

The airforce service imposes a 60-second cooldown between successful generations. Add a counting down timer e.g. Generate (60), Generate (59) on the Generate button face itself. This would not act as a hard controls lock or prevent requests, it's simply a friendly timer that starts only after a successful return/download to remind the user, but never prevents user actions. This timer is global for the API key being used, so all models share the cooldown. No persistence for the timer, keep it minimal and lightweight.

No backwards compatibility, if you want to rename a handler because it has "image" in it, then rename it. We'll deal with the fallout.

Additional dependencies for the project are OK as long as they are appropriate.

### PROJECT 

Image Assistant is a PyQt6 desktop application that transforms user concepts into optimized image generation prompts via AI services (Gemini, NVIDIA NIM), with integrated text-to-image synthesis through Pollinations, Airforce, and Perchance APIs.

### DELIVERABLES

Please output a brief summary including any design choices, and the updated or new files where applicable. You have authority to create, delete, or consolidate services or modules. If only small changes to existing files are required, please output them in

SEARCH: 

```
...stuff...
``` 

REPLACE:

```
...stuff...
``` 

style blocks. If no significant improvements can be made, you are free to make that judgment.

### CONTEXT

## 🎯 Focused Context (Agent-Selected)

**Project Root:** `image-prompter/`
**Files Included:** 8

---

### File Index

1. `gui/widgets/airforce_page.py`
2. `core/services/airforce_service.py`
3. `core/config.py`
4. `gui/widgets/gallery_page.py`
5. `core/services/gallery_service.py`
6. `core/utils.py`
7. `gui/widgets/image_gen_common.py`
8. `gui/widgets/media_panel.py`

---

### `gui/widgets/airforce_page.py`

```python
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
from core.utils import reveal_file_in_explorer


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
        """Open file explorer and select the current image."""
        if self._current_image_path and os.path.isfile(self._current_image_path):
            reveal_file_in_explorer(self._current_image_path)
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
```

### `core/services/airforce_service.py`

```python
# core/services/airforce_service.py
"""
Airforce AI Image Generation Service.
Handles API communication with Airforce for text-to-image generation via SSE.
"""

import os
import json
import base64
import urllib.request
import urllib.error
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from core.utils import save_generated_image


class AirforceWorker(QThread):
    """Worker thread for Airforce API image generation."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    API_URL = "https://api.airforce/v1/images/generations"

    def __init__(self, prompt, negative_prompt, model, size, seed):
        super().__init__()
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.model = model
        self.size = size
        self.seed = seed
        self._is_cancelled = False
        self.api_key = os.environ.get("AIRFORCE_API_KEY", "")

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.api_key:
                self.error.emit("AIRFORCE_API_KEY environment variable not set.")
                return

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ImagePrompter/1.0",
            }

            payload = {
                "model": self.model,
                "prompt": self.prompt,
                "n": 1,
                "size": self.size,
                "response_format": "b64_json",
                "sse": True,
            }

            if self.negative_prompt:
                payload["negative_prompt"] = self.negative_prompt
            if self.seed != -1:
                payload["seed"] = self.seed

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.API_URL, data=data_bytes, headers=headers, method="POST"
            )

            b64_data = None
            raw_body = b""

            with urllib.request.urlopen(req, timeout=180) as response:
                for raw_line in response:
                    if self._is_cancelled:
                        self.error.emit("Generation cancelled.")
                        return

                    raw_body += raw_line
                    line_str = raw_line.decode("utf-8").strip()

                    if not line_str:
                        continue
                    if line_str in ("data: [DONE]", "data: : keepalive"):
                        continue
                    if not line_str.startswith("data: "):
                        continue

                    try:
                        chunk = json.loads(line_str[6:])
                    except json.JSONDecodeError:
                        continue

                    b64_data = self._extract_b64(chunk)
                    if b64_data:
                        break

            if self._is_cancelled:
                self.error.emit("Generation cancelled.")
                return

            # Fallback: try parsing entire response body as JSON
            if not b64_data:
                try:
                    full_data = json.loads(raw_body.decode("utf-8"))
                    b64_data = self._extract_b64(full_data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

            if not b64_data:
                self.error.emit("No image data received from API.")
                return

            image_bytes = base64.b64decode(b64_data)
            filepath = save_generated_image(
                image_bytes, self.prompt, self.negative_prompt,
                self.model, self.size, self.seed, "Airforce",
            )
            self.finished.emit(filepath)

        except urllib.error.HTTPError as e:
            if not self._is_cancelled:
                body = ""
                try:
                    body = e.read(500).decode("utf-8", errors="replace")
                except Exception:
                    pass
                self.error.emit(f"HTTP {e.code}: {body or e.reason}")
        except urllib.error.URLError as e:
            if not self._is_cancelled:
                self.error.emit(f"Connection error: {e.reason}")
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))

    @staticmethod
    def _extract_b64(data) -> Optional[str]:
        """Extract base64 image data from an API response dict."""
        if not isinstance(data, dict):
            return None
        # OpenAI-style: {"data": [{"b64_json": "..."}]}
        if "data" in data and isinstance(data["data"], list):
            for item in data["data"]:
                if isinstance(item, dict) and "b64_json" in item:
                    return item["b64_json"]
        # Flat: {"b64_json": "..."}
        if "b64_json" in data:
            return data["b64_json"]
        return None


class AirforceService(QObject):
    """Service for Airforce AI image generation."""

    image_generated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.worker = None

    def generate_image(self, prompt, negative_prompt="", model="grok-imagine",
                       size="1024x1024", seed=-1):
        """Start image generation in a background thread."""
        if not prompt.strip():
            self.error_occurred.emit("Prompt cannot be empty.")
            self.status_updated.emit("Error: Prompt cannot be empty.")
            return

        self.status_updated.emit(f"Generating with {model} ({size})...")

        self.worker = AirforceWorker(prompt, negative_prompt, model, size, seed)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, filepath):
        if self.sender() is not self.worker:
            return
        self.worker = None
        self.image_generated.emit(filepath)
        self.status_updated.emit(f"Image saved: {filepath}")

    def _on_error(self, msg):
        if self.sender() is not self.worker:
            return
        self.worker = None
        self.error_occurred.emit(msg)
        self.status_updated.emit(f"Error: {msg}")

    def cancel_generation(self):
        """Cancel the current generation if running."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
```

### `core/config.py`

```python
"""Configuration Manager for PyQt6 GUI Framework."""
import os
import json

_DEFAULTS = {
    "window_width": 1200,
    "window_height": 800,
    "theme": "dark",
    "current_service": "Gemini",
    "current_model": "Flash",
    "default_system_prompt": "You are a helpful AI assistant.",
    "splitter_sizes": [780, 420],
    "media_active_tab": 0,
    "gallery_page": 1,
    "gallery_filter": "All",
    "pollinations_positive_prompt": "",
    "pollinations_negative_prompt": "",
    "pollinations_model": "zimage",
    "pollinations_size": "1024x1024",
    "pollinations_seed": -1,
    "pollinations_last_image": "",
    "airforce_positive_prompt": "",
    "airforce_negative_prompt": "",
    "airforce_model": "grok-imagine",
    "airforce_size": "1024x1024",
    "airforce_seed": -1,
    "airforce_last_image": "",
    "perchance_url": "https://perchance.org/a1481832-0a06-414f-baa6-616052e5f61d",
    "adblocker": {
        "blocked_domains": [
            "a.pub.network",
            "d.pub.network",
            "cdn.snigelweb.com",
            "googletagmanager.com",
            "cloudflareinsights.com",
            "static.criteo.net",
            "secure.quantserve.com",
            "fundingchoicesmessages.google.com"
        ],
        "hidden_selectors": [
            ".ad-providers-ctn-el",
            "#adCtn",
            "#pmLink"
        ]
    },
    "display_fields": {
        "core": True,
        "composition": True,
        "lighting": True,
        "style": True,
        "technical": True,
        "post_processing": True,
        "special_elements": True,
        "detailed_prompt": True,
        "grok_imagine_optimized": True,
        "gemini_optimized": True,
        "flux_optimized": True,
        "stable_diffusion_optimized": True,
        "video_optimized": True
    }
}

class ConfigManager:
    """Manages GUI configuration values and local gui_config.json persistence."""

    def __init__(self, config_file: str = "gui_config.json"):
        self.config_file = config_file
        self.__dict__.update(_DEFAULTS)
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                for k in _DEFAULTS:
                    val = config.get(k, getattr(self, k))
                    if isinstance(val, dict) and isinstance(_DEFAULTS[k], dict):
                        merged = _DEFAULTS[k].copy()
                        merged.update(val)
                        setattr(self, k, merged)
                    else:
                        setattr(self, k, val)
                if "default_service" in config and "current_service" not in config:
                    self.current_service = config["default_service"]
                if "service_models" in config and "current_model" not in config:
                    self.current_model = config.get("service_models", {}).get(self.current_service, self.current_model)
        except Exception:
            pass

    def save(self) -> None:
        try:
            with open(self.config_file, 'w') as f:
                json.dump({k: getattr(self, k) for k in _DEFAULTS}, f, indent=2)
        except Exception:
            pass
```

### `gui/widgets/gallery_page.py`

```python
# gui/widgets/gallery_page.py
"""
Gallery Page - Displays generated images in a responsive 4x3 grid.
Includes pagination, filtering, and prompt copying functionalities.
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QEvent
from PyQt6.QtGui import QCursor

from gui.widgets.image_gen_common import ImageDisplay, BTN_DROPDOWN, make_dropdown
from core.utils import reveal_file_in_explorer
from core.services.gallery_service import GalleryService


class ElidedLabel(QLabel):
    """A QLabel that elides its text on the right if it exceeds widget width."""
    clicked = pyqtSignal()
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        
    def setText(self, text):
        self._full_text = text
        super().setText(text)
        self.update_elision()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elision()
        
    def update_elision(self):
        fm = self.fontMetrics()
        w = max(0, self.width() - 2)
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, w)
        super().setText(elided)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class GalleryItemWidget(QWidget):
    """Individual container for an image, prompt, and metadata in the Gallery grid."""
    prompt_copied = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filepath = ""
        self.prompt = ""
        
        self.setStyleSheet("""
            GalleryItemWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        
        # Force uniform sizing and prevent layout collapse when hidden
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        self.image_display = ImageDisplay()
        self.image_display.setMinimumSize(32, 32)
        
        self.prompt_label = ElidedLabel()
        self.prompt_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prompt_label.setStyleSheet("color: #ccc; font-size: 11px; border: none; background: transparent;")
        self.prompt_label.setToolTip("Click to copy prompt")
        
        self.meta_label = ElidedLabel()
        self.meta_label.setStyleSheet("color: #888; font-size: 10px; border: none; background: transparent;")
        
        layout.addWidget(self.image_display, stretch=1)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.meta_label)
        
        self.image_display.clicked.connect(self._on_image_clicked)
        self.prompt_label.clicked.connect(self._on_prompt_clicked)
        
    def set_data(self, meta):
        self.filepath = meta.filepath
        self.prompt = meta.prompt
        self.image_display.set_image(meta.filepath)
        
        display_prompt = self.prompt.replace('\n', ' ').strip()
        if not display_prompt:
            display_prompt = "No prompt"
            
        self.prompt_label.setText(display_prompt)
        
        try:
            dt = datetime.strptime(meta.timestamp, "%Y-%m-%d_%H-%M-%S")
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts_str = meta.timestamp
            
        self.meta_label.setText(f"{meta.service} | {meta.model} | {ts_str}")
        self.show()
        
    def clear(self):
        self.filepath = ""
        self.prompt = ""
        self.image_display.clear_image()
        self.prompt_label.setText("")
        self.meta_label.setText("")
        self.hide()
        
    def _on_image_clicked(self):
        if self.filepath:
            reveal_file_in_explorer(self.filepath)
            
    def _on_prompt_clicked(self):
        if self.prompt:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.prompt)
            self.prompt_copied.emit("Prompt copied to clipboard.")


class GalleryPage(QWidget):
    """Media Gallery page displaying generated images in a paginated grid."""
    status_updated = pyqtSignal(str)
    
    FILTERS = ["All", "Pollinations", "Airforce", "Perchance"]
    ITEMS_PER_PAGE = 12

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.service = GalleryService()
        
        self.images = []
        self.current_page = 1
        self.total_pages = 1
        self.current_filter = "All"
        self._items = []
        
        self.active_dropdown = None
        self.hide_timer = QTimer()
        self.hide_timer.setInterval(250)
        self.hide_timer.timeout.connect(self._hide_dropdown)
        
        self._build_ui()
        self._load_from_config()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Controls Bar ---
        controls = QWidget()
        controls.setStyleSheet("background-color: #121212;")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(6)
        
        cl.addStretch(1)
        
        # Internal Page Pagination
        paginator_layout = QHBoxLayout()
        paginator_layout.setSpacing(2)
        
        self.first_btn = QPushButton("«")
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.last_btn = QPushButton("»")
        
        for btn in [self.first_btn, self.prev_btn, self.next_btn, self.last_btn]:
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(BTN_DROPDOWN)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            paginator_layout.addWidget(btn)
            
        self.first_btn.clicked.connect(lambda: self.set_page(1))
        self.prev_btn.clicked.connect(lambda: self.set_page(self.current_page - 1))
        self.next_btn.clicked.connect(lambda: self.set_page(self.current_page + 1))
        self.last_btn.clicked.connect(self._goto_last_page)
        
        self.page_label = QLabel("Page 1 of 1 (0 items)")
        self.page_label.setStyleSheet("color: #ccc; font-size: 11px; padding: 0 8px;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        paginator_layout.insertWidget(2, self.page_label)
        cl.addLayout(paginator_layout)
        
        cl.addStretch(1)
        
        # Display Filtering Toggles
        self.filter_btn = QPushButton(self.current_filter)
        self.filter_btn.setStyleSheet(BTN_DROPDOWN)
        self.filter_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.filter_btn.setMinimumWidth(100)
        
        self.filter_dropdown = make_dropdown(self, self.FILTERS, self._on_filter_selected, self)
        self.filter_btn.installEventFilter(self)
        
        cl.addWidget(self.filter_btn)
        layout.addWidget(controls)
        
        # --- Grid Area ---
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: #2a2a2a;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(8)
        
        for row in range(3):
            self.grid_layout.setRowStretch(row, 1)
            for col in range(4):
                if row == 0:
                    self.grid_layout.setColumnStretch(col, 1)
                item = GalleryItemWidget()
                item.prompt_copied.connect(self.status_updated.emit)
                self.grid_layout.addWidget(item, row, col)
                self._items.append(item)
                
        layout.addWidget(self.grid_container, stretch=1)

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.Enter:
            if obj == self.filter_btn:
                self._show_dropdown(self.filter_dropdown, self.filter_btn)
            elif obj == self.filter_dropdown:
                self.hide_timer.stop()
        elif et == QEvent.Type.Leave:
            if obj in (self.filter_btn, self.filter_dropdown):
                self.hide_timer.start()
        return super().eventFilter(obj, event)

    def _show_dropdown(self, dropdown, button):
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

    def _on_filter_selected(self, filter_name: str):
        self.current_filter = filter_name
        self.filter_btn.setText(filter_name)
        self._hide_dropdown()
        self.current_page = 1
        self._save_to_config()
        self.refresh()
        
    def _save_to_config(self):
        if not self.config_manager:
            return
        self.config_manager.gallery_page = self.current_page
        self.config_manager.gallery_filter = self.current_filter
        self.config_manager.save()
        
    def _load_from_config(self):
        if not self.config_manager:
            return
        self.current_page = getattr(self.config_manager, "gallery_page", 1)
        self.current_filter = getattr(self.config_manager, "gallery_filter", "All")
        if self.current_filter in self.FILTERS:
            self.filter_btn.setText(self.current_filter)

    def refresh(self):
        self.images = self.service.get_images(self.current_filter)
        self.total_pages = max(1, (len(self.images) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        self._update_display()
        
    def _goto_last_page(self):
        self.set_page(self.total_pages)

    def set_page(self, page: int):
        if 1 <= page <= self.total_pages and page != self.current_page:
            self.current_page = page
            self._save_to_config()
            self._update_display()

    def _update_display(self):
        start_idx = (self.current_page - 1) * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_images = self.images[start_idx:end_idx]
        
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages} ({len(self.images)} items)")
        
        self.first_btn.setEnabled(self.current_page > 1)
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
        self.last_btn.setEnabled(self.current_page < self.total_pages)
        
        for i, item_widget in enumerate(self._items):
            if i < len(page_images):
                item_widget.set_data(page_images[i])
            else:
                item_widget.clear()

    def hideEvent(self, event):
        self._hide_dropdown()
        super().hideEvent(event)
```

### `core/services/gallery_service.py`

```python
# core/services/gallery_service.py
"""
Gallery Service - Reads and caches image metadata from the generated images directory.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ImageMetadata:
    filepath: str
    prompt: str
    service: str
    model: str
    timestamp: str


class GalleryService:
    def __init__(self):
        self._cache: Dict[str, tuple[float, ImageMetadata]] = {}
        self.images_dir = Path("images")
        self.images_dir.mkdir(exist_ok=True)
        
    def get_images(self, filter_service: str = "All") -> List[ImageMetadata]:
        images = []
        if not self.images_dir.exists():
            return images
            
        for p in self.images_dir.glob("*.jpg"):
            try:
                mtime = p.stat().st_mtime
                filepath_str = str(p)
                
                # Check cache mapping via modified time
                if filepath_str in self._cache and self._cache[filepath_str][0] == mtime:
                    meta = self._cache[filepath_str][1]
                else:
                    meta = self._parse_metadata(p)
                    self._cache[filepath_str] = (mtime, meta)
                    
                if filter_service == "All" or meta.service.lower() == filter_service.lower():
                    images.append(meta)
            except Exception:
                continue
                
        # Sort by filepath descending (newest timestamp first)
        images.sort(key=lambda x: x.filepath, reverse=True)
        return images
        
    def _parse_metadata(self, filepath: Path) -> ImageMetadata:
        prompt = ""
        service = "Unknown"
        model = "Unknown"
        timestamp = filepath.stem
        
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                exif = img.getexif()
                if exif and 0x010E in exif:
                    meta_str = exif[0x010E]
                    parts = [p.strip() for p in meta_str.split("|")]
                    for part in parts:
                        if part.startswith("Prompt:"):
                            prompt = part[7:].strip()
                        elif part.startswith("Service:"):
                            service = part[8:].strip()
                        elif part.startswith("Model:"):
                            model = part[6:].strip()
        except Exception:
            pass
            
        return ImageMetadata(str(filepath), prompt, service, model, timestamp)
```

### `core/utils.py`

```python
# core/utils.py
"""Shared utility functions for the application."""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path


def reveal_file_in_explorer(filepath: str) -> bool:
    """
    Open the system file explorer and select/highlight the given file.

    Platform behavior:
        Windows: explorer /select,<path>
        macOS:   open -R <path>
        Linux:   xdg-open <parent directory>

    Returns True if the command was launched, False on error or missing file.
    """
    filepath = os.path.normpath(os.path.abspath(filepath))
    if not os.path.exists(filepath):
        return False
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{filepath}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
        return True
    except Exception:
        return False


def open_file(filepath: str) -> bool:
    """
    Open a file with the system's default application.

    Returns True if the command was launched, False on error or missing file.
    """
    filepath = os.path.normpath(os.path.abspath(filepath))
    if not os.path.exists(filepath):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", filepath])
        else:
            subprocess.Popen(["xdg-open", filepath])
        return True
    except Exception:
        return False


def save_generated_image(
    image_data: bytes,
    prompt: str,
    negative_prompt: str,
    model: str,
    size: str,
    seed: int,
    service: str,
) -> str:
    """Save generated image to the images/ directory with embedded EXIF metadata.

    Uses a timestamp-based filename (``YYYY-MM-DD_HH-MM-SS.jpg``) and embeds
    prompt / generation metadata into the EXIF ImageDescription tag when
    Pillow is available.

    Args:
        image_data:      Raw image bytes (any format Pillow can open).
        prompt:          Positive prompt text.
        negative_prompt: Negative prompt text (may be empty).
        model:           Model identifier string.
        size:            Size string, e.g. ``"1024x1024"``.
        seed:            Seed value used for generation.
        service:         Service name (e.g. ``"Pollinations"``, ``"Airforce"``).

    Returns:
        The absolute-ish path to the saved file as a string.
    """
    images_dir = Path("images")
    images_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = images_dir / f"{timestamp}.jpg"
    counter = 1
    while filepath.exists():
        filepath = images_dir / f"{timestamp}_{counter}.jpg"
        counter += 1

    metadata_str = (
        f"Prompt: {prompt} | "
        f"Negative: {negative_prompt or 'None'} | "
        f"Model: {model} | "
        f"Size: {size} | "
        f"Seed: {seed} | "
        f"Service: {service}"
    )

    saved_with_meta = False
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        exif = img.getexif()
        exif[0x010E] = metadata_str        # ImageDescription
        exif[0x0131] = f"{service} AI"     # Software
        img.save(str(filepath), "JPEG", quality=95, exif=exif.tobytes())
        saved_with_meta = True
    except Exception:
        pass

    if not saved_with_meta:
        with open(filepath, "wb") as f:
            f.write(image_data)

    return str(filepath)
```

### `gui/widgets/image_gen_common.py`

```python
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
```

### `gui/widgets/media_panel.py`

```python
# gui/widgets/media_panel.py
"""
Media Panel - Secondary pane for generative imaging interfacing.
Provides tabbed navigation for different image generation APIs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from gui.widgets.pollinations_page import PollinationsPage
from gui.widgets.airforce_page import AirforcePage
from gui.widgets.perchance_page import PerchancePage


class MediaPanel(QWidget):
    """Secondary pane with tabbed navigation for image generation API interfaces."""

    status_updated = pyqtSignal(str)

    TAB_NAMES = ["Gallery", "Pollinations", "Airforce", "Perchance"]

    ACTIVE_BG = "#1E88E5"
    ACTIVE_HOVER = "#2A9BF8"
    INACTIVE_BG = "#2a2a2a"
    INACTIVE_HOVER = "#3d3d3d"

    _TAB_ICONS = {"Gallery": "🖼️", "Pollinations": "🌸", "Airforce": "✈️", "Perchance": "🎲"}
    _TAB_DESCS = {
        "Gallery": "Generated images will appear here",
        "Pollinations": "Pollinations AI image generation",
        "Airforce": "Airforce image generation API",
        "Perchance": "Perchance image generation",
    }

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._current_tab = 0
        self._tabs = []
        self._build_ui()
        self._load_active_tab()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Tab bar ---
        tab_bar = QWidget()
        tab_bar.setFixedHeight(34)
        tab_bar.setStyleSheet("background-color: #1a1a1a;")
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(1)

        for i, name in enumerate(self.TAB_NAMES):
            btn = QPushButton(name)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self._tabs.append(btn)
            tab_layout.addWidget(btn)

        layout.addWidget(tab_bar)

        # --- Stacked content area ---
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #2a2a2a; border: 1px solid #333;")

        from gui.widgets.gallery_page import GalleryPage
        for name in self.TAB_NAMES:
            if name == "Gallery":
                self.gallery_page = GalleryPage(self.config_manager)
                self.gallery_page.status_updated.connect(self.status_updated.emit)
                self._stack.addWidget(self.gallery_page)
            elif name == "Pollinations":
                self.pollinations_page = PollinationsPage(self.config_manager)
                self.pollinations_page.status_updated.connect(self.status_updated.emit)
                self._stack.addWidget(self.pollinations_page)
            elif name == "Airforce":
                self.airforce_page = AirforcePage(self.config_manager)
                self.airforce_page.status_updated.connect(self.status_updated.emit)
                self._stack.addWidget(self.airforce_page)
            elif name == "Perchance":
                self.perchance_page = PerchancePage(self.config_manager)
                self.perchance_page.status_updated.connect(self.status_updated.emit)
                self._stack.addWidget(self.perchance_page)
            else:
                self._stack.addWidget(self._create_page(name))

        layout.addWidget(self._stack, 1)
        self._update_tab_styles()

    def _create_page(self, name: str) -> QWidget:
        """Create a placeholder page for a tab."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel(self._TAB_ICONS.get(name, "📄"))
        icon.setStyleSheet("font-size: 32pt;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(icon)

        title = QLabel(name)
        title.setStyleSheet("color: #666; font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(title)

        desc = QLabel(self._TAB_DESCS.get(name, ""))
        desc.setStyleSheet("color: #444; font-size: 9pt;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        page_layout.addWidget(desc)

        return page

    def _switch_tab(self, index: int):
        """Switch to the specified tab index."""
        if index == self._current_tab:
            return
        self._current_tab = index
        self._stack.setCurrentIndex(index)
        self._update_tab_styles()
        
        current_widget = self._stack.widget(index)
        if hasattr(current_widget, "refresh"):
            current_widget.refresh()
            
        if self.config_manager:
            self.config_manager.media_active_tab = index
            self.config_manager.save()

    def _load_active_tab(self):
        """Restore the last active tab from config."""
        if self.config_manager:
            tab = getattr(self.config_manager, 'media_active_tab', 0)
            if 0 <= tab < len(self.TAB_NAMES):
                self._current_tab = tab
                self._stack.setCurrentIndex(tab)
                self._update_tab_styles()

    def _update_tab_styles(self):
        """Update tab button visual styles based on active selection."""
        for i, btn in enumerate(self._tabs):
            if i == self._current_tab:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.ACTIVE_BG};
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 9pt;
                        border: none;
                        border-radius: 0px;
                        padding: 4px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {self.ACTIVE_HOVER};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.INACTIVE_BG};
                        color: #888;
                        font-size: 9pt;
                        border: none;
                        border-radius: 0px;
                        padding: 4px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {self.INACTIVE_HOVER};
                        color: #fff;
                    }}
                """)
```