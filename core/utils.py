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