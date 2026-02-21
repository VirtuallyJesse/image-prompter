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