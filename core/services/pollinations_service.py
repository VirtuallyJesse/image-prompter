# core/services/pollinations_service.py
"""
Pollinations AI Image Generation Service.
Handles API communication with Pollinations for text-to-image generation.
"""

import os
import urllib.request
import urllib.parse
import urllib.error

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from core.utils import save_generated_image


class PollinationsWorker(QThread):
    """Worker thread for Pollinations API image generation."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    BASE_URL = "https://gen.pollinations.ai/image"

    def __init__(self, prompt, negative_prompt, model, width, height, seed):
        super().__init__()
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.model = model
        self.width = width
        self.height = height
        self.seed = seed
        self._is_cancelled = False
        self.api_key = os.environ.get("POLLINATIONS_API_KEY", "")

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            encoded_prompt = urllib.parse.quote(self.prompt, safe="")
            params = {
                "model": self.model,
                "width": self.width,
                "height": self.height,
                "seed": self.seed,
                "nologo": "true",
            }
            if self.negative_prompt:
                params["negative_prompt"] = self.negative_prompt

            query_string = urllib.parse.urlencode(params)
            full_url = f"{self.BASE_URL}/{encoded_prompt}?{query_string}"

            headers = {"User-Agent": "ImagePrompter/1.0"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            req = urllib.request.Request(full_url, headers=headers)
            response = urllib.request.urlopen(req, timeout=180)

            if self._is_cancelled:
                self.error.emit("Generation cancelled.")
                return

            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type:
                body = response.read(500).decode("utf-8", errors="replace")
                self.error.emit(f"Unexpected response ({content_type}): {body}")
                return

            image_data = response.read()

            if self._is_cancelled:
                self.error.emit("Generation cancelled.")
                return

            filepath = save_generated_image(
                image_data, self.prompt, self.negative_prompt,
                self.model, f"{self.width}x{self.height}", self.seed,
                "Pollinations",
            )
            self.finished.emit(filepath)

        except urllib.error.HTTPError as e:
            if not self._is_cancelled:
                body = ""
                try:
                    body = e.read(300).decode("utf-8", errors="replace")
                except Exception:
                    pass
                self.error.emit(f"HTTP {e.code}: {body or e.reason}")
        except urllib.error.URLError as e:
            if not self._is_cancelled:
                self.error.emit(f"Connection error: {e.reason}")
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))

class PollinationsService(QObject):
    """Service for Pollinations AI image generation."""
    image_generated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.worker = None

    def generate_image(self, prompt, negative_prompt="", model="zimage",
                       width=1024, height=1024, seed=-1):
        """Start image generation in a background thread."""
        if not prompt.strip():
            self.error_occurred.emit("Prompt cannot be empty.")
            self.status_updated.emit("Error: Prompt cannot be empty.")
            return

        self.status_updated.emit(f"Generating with {model} ({width}x{height})...")

        self.worker = PollinationsWorker(
            prompt, negative_prompt, model, width, height, seed
        )
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