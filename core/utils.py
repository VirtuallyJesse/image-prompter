# core/utils.py
"""Shared utility functions for the application."""

import os
import sys
import subprocess


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
