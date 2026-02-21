# core/services/pollinations_service.py
"""
Pollinations AI Image Generation Service.
Handles API communication with Pollinations for text-to-image generation.
"""

import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QThread


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

            filepath = self._save_image(image_data)
            self.finished.emit(str(filepath))

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

    def _save_image(self, image_data: bytes) -> Path:
        """Save image data to disk, embedding metadata when possible."""
        images_dir = Path("images")
        images_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = images_dir / f"{timestamp}.jpg"
        counter = 1
        while filepath.exists():
            filepath = images_dir / f"{timestamp}_{counter}.jpg"
            counter += 1

        metadata_str = (
            f"Prompt: {self.prompt} | "
            f"Negative: {self.negative_prompt or 'None'} | "
            f"Model: {self.model} | "
            f"Size: {self.width}x{self.height} | "
            f"Seed: {self.seed} | "
            f"Service: Pollinations"
        )

        saved_with_meta = False
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_data))
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            exif = img.getexif()
            exif[0x010E] = metadata_str       # ImageDescription
            exif[0x0131] = "Pollinations AI"  # Software
            img.save(str(filepath), "JPEG", quality=95, exif=exif.tobytes())
            saved_with_meta = True
        except Exception:
            pass

        if not saved_with_meta:
            with open(filepath, "wb") as f:
                f.write(image_data)

        return filepath


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