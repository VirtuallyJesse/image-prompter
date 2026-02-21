# core/services/perchance_service.py
"""
Perchance Service – WebEngine profile management, ad blocking, and image
download handling for the embedded Perchance image generator.
"""

import os
from datetime import datetime
from pathlib import Path

_WEBENGINE_AVAILABLE = False
try:
    from PyQt6.QtWebEngineCore import (
        QWebEngineProfile,
        QWebEnginePage,
        QWebEngineUrlRequestInterceptor,
    )
    _WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineUrlRequestInterceptor = None


def is_webengine_available() -> bool:
    """Return *True* if PyQt6-WebEngine is installed and importable."""
    return _WEBENGINE_AVAILABLE


# ── Ad-block request interceptor ───────────────────────────────────────────

if _WEBENGINE_AVAILABLE:

    class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
        """Block network requests whose URL contains a blocked-domain substring."""

        def __init__(self, blocked_domains: list, parent=None):
            super().__init__(parent)
            self.blocked_domains = blocked_domains or []

        def interceptRequest(self, info):
            url = info.requestUrl().toString()
            for domain in self.blocked_domains:
                if domain in url:
                    info.block(True)
                    return


# ── Service class ──────────────────────────────────────────────────────────

class PerchanceService:
    """
    Creates a persistent WebEngine profile with ad-blocking and handles
    image downloads from the embedded Perchance page.
    """

    DEFAULT_BLOCKED_DOMAINS = [
        "a.pub.network",
        "d.pub.network",
        "cdn.snigelweb.com",
        "googletagmanager.com",
        "cloudflareinsights.com",
        "static.criteo.net",
        "secure.quantserve.com",
        "fundingchoicesmessages.google.com",
    ]

    DEFAULT_HIDDEN_SELECTORS = [
        ".ad-providers-ctn-el",
        "#adCtn",
        "#pmLink",
    ]

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self._profile = None
        self._interceptor = None
        self._page = None
        self._status_callback = None

    # -- External setters ------------------------------------------------

    def set_page(self, page):
        """Store a reference to the active QWebEnginePage for JS access."""
        self._page = page

    def set_status_callback(self, callback):
        """Register a callable for status messages (e.g. a pyqtSignal emit)."""
        self._status_callback = callback

    def _emit_status(self, msg: str):
        if self._status_callback:
            self._status_callback(msg)

    # ── Profile creation ────────────────────────────────────────────────

    def create_profile(self, parent=None):
        """
        Build a *persistent* QWebEngineProfile:

        * Disk-backed cookies (login survives restarts)
        * Ad-blocking request interceptor
        * Download-requested handler for saving images

        Returns the profile, or ``None`` when WebEngine is unavailable.
        """
        if not _WEBENGINE_AVAILABLE:
            return None

        from PyQt6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        storage_root = os.path.join(base, "webengine", "perchance")
        os.makedirs(storage_root, exist_ok=True)

        profile = QWebEngineProfile("perchance", parent)
        profile.setPersistentStoragePath(os.path.join(storage_root, "storage"))
        profile.setCachePath(os.path.join(storage_root, "cache"))
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)

        try:
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
        except AttributeError:
            pass  # older PyQt6 build without this enum

        # Layer 1 – network-level ad blocking
        blocked = self._get_blocked_domains()
        if blocked:
            self._interceptor = AdBlockInterceptor(blocked, parent)
            profile.setUrlRequestInterceptor(self._interceptor)

        # Image download handling
        profile.downloadRequested.connect(self._on_download_requested)

        self._profile = profile
        return profile

    # ── Ad-hide JavaScript (Layer 2) ────────────────────────────────────

    def get_ad_hide_script(self) -> str:
        """
        Return a JavaScript snippet that hides ad-related DOM elements and
        watches for dynamically inserted ones via MutationObserver.
        """
        selectors = self._get_hidden_selectors()
        if not selectors:
            return ""

        selectors_js = ", ".join(f'"{s}"' for s in selectors)
        return f"""
(function() {{
    if (window._perchanceAdblockActive) return;
    window._perchanceAdblockActive = true;

    var selectors = [{selectors_js}];

    function hide() {{
        selectors.forEach(function(s) {{
            document.querySelectorAll(s).forEach(function(el) {{
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
                el.style.position = 'absolute';
                el.style.left = '-9999px';
            }});
        }});
    }}

    hide();
    setTimeout(hide, 1000);
    setTimeout(hide, 3000);

    var obs = new MutationObserver(function() {{ hide(); }});
    if (document.body) {{
        obs.observe(document.body, {{ childList: true, subtree: true }});
    }} else {{
        document.addEventListener('DOMContentLoaded', function() {{
            hide();
            obs.observe(document.body, {{ childList: true, subtree: true }});
        }});
    }}
}})();
"""

    # ── Download handling ───────────────────────────────────────────────

    def _on_download_requested(self, download):
        """
        Accept image downloads and redirect them to ``images/`` with a
        timestamp-based temporary filename.  Non-image downloads are
        silently ignored.
        """
        try:
            mime_type = (download.mimeType() or "").lower()
            dl_name = (download.downloadFileName() or "").lower()
            is_image = mime_type.startswith("image/") or dl_name.endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".gif")
            )
            if not is_image:
                return

            images_dir = Path("images")
            images_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            orig_ext = Path(download.downloadFileName() or "image.png").suffix or ".png"
            temp_name = f"_perchance_tmp_{timestamp}{orig_ext}"

            download.setDownloadDirectory(str(images_dir.resolve()))
            download.setDownloadFileName(temp_name)

            # Best-effort prompt capture via async JS callback
            captured = {"prompt": ""}
            if self._page:
                self._page.runJavaScript(
                    "(function(){var e=document.querySelector('textarea');"
                    "return e?e.value:'';})()",
                    lambda result, c=captured: c.update({"prompt": result or ""}),
                )

            temp_path = images_dir / temp_name

            download.isFinishedChanged.connect(
                lambda tp=temp_path, ts=timestamp, cap=captured: self._finalize_download(
                    tp, ts, cap
                )
            )

            download.accept()
            self._emit_status("Downloading image from Perchance\u2026")

        except Exception as e:
            self._emit_status(f"Download error: {e}")

    def _finalize_download(self, temp_path: Path, timestamp: str, captured: dict):
        """
        Post-process a completed download:

        1. Open with Pillow (if available)
        2. Convert to RGB JPEG
        3. Embed EXIF metadata (prompt + service)
        4. Remove the temporary file

        Falls back to a simple rename when Pillow is absent.
        """
        if not temp_path.exists():
            return
        try:
            if temp_path.stat().st_size == 0:
                temp_path.unlink(missing_ok=True)
                return
        except OSError:
            return

        images_dir = temp_path.parent
        prompt = captured.get("prompt", "")

        # Determine unique final path
        final_path = images_dir / f"{timestamp}.jpg"
        counter = 1
        while final_path.exists():
            final_path = images_dir / f"{timestamp}_{counter}.jpg"
            counter += 1

        saved = False
        try:
            from PIL import Image

            img = Image.open(str(temp_path))
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            parts = []
            if prompt:
                parts.append(f"Prompt: {prompt}")
            parts.append("Service: Perchance")
            metadata_str = " | ".join(parts)

            exif = img.getexif()
            exif[0x010E] = metadata_str      # ImageDescription
            exif[0x0131] = "Perchance AI"    # Software
            img.save(str(final_path), "JPEG", quality=95, exif=exif.tobytes())
            saved = True
        except ImportError:
            pass
        except Exception as e:
            self._emit_status(f"Image conversion note: {e}")

        if not saved:
            # Fallback: rename temp file directly
            try:
                temp_path.rename(final_path)
                saved = True
            except OSError:
                pass

        # Clean up temp file (Pillow path leaves it behind)
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

        if saved:
            self._emit_status(f"Image saved: {final_path.name}")

    # ── Config helpers ──────────────────────────────────────────────────

    def _get_blocked_domains(self) -> list:
        if self.config_manager:
            ab = getattr(self.config_manager, "adblocker", {})
            if isinstance(ab, dict) and ab.get("blocked_domains"):
                return ab["blocked_domains"]
        return self.DEFAULT_BLOCKED_DOMAINS

    def _get_hidden_selectors(self) -> list:
        if self.config_manager:
            ab = getattr(self.config_manager, "adblocker", {})
            if isinstance(ab, dict) and ab.get("hidden_selectors"):
                return ab["hidden_selectors"]
        return self.DEFAULT_HIDDEN_SELECTORS