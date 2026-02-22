# core/services/perchance_service.py
"""
Perchance Service – WebEngine profile management, ad blocking, auto-download
interception, and EXIF metadata embedding for the embedded Perchance generator.

Auto-download works by injecting JavaScript into all frames (at the profile
level, at DocumentCreation time) that intercepts Perchance's internal
postMessage pipeline.  Generator sub-frames capture ``finished`` messages,
extract metadata from iframe URL hashes, and forward everything to the top
frame.  Python polls the top frame's queue every second and saves images
with comprehensive EXIF metadata.

Manual downloads (browser "save to device") fall back to metadata captured
from the most recently auto-downloaded image.
"""

import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    both automatic and manual image downloads with full EXIF metadata.
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
        "#menuBarEl",
        "#minimalModeMenuBtn",
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
        * Download-requested handler for manual image saves

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

        # Manual download fallback (browser "save to device")
        profile.downloadRequested.connect(self._on_download_requested)

        self._profile = profile
        return profile

    # ── Manual download handling ────────────────────────────────────────

    def _on_download_requested(self, download):
        """
        Handle manual 'save to device' downloads.  Captures full metadata
        from the auto-download listener's stored state so the saved image
        receives the same EXIF tags as auto-downloaded images.
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
            temp_path = images_dir / temp_name

            # Capture metadata from the auto-download listener's top-frame state.
            # The JS callback fires asynchronously but completes before the
            # download finishes writing to disk.
            captured: dict = {}
            if self._page:
                self._page.runJavaScript(
                    """(function(){
                        var m = window._perchanceLastMeta;
                        if (!m) return '{}';
                        return JSON.stringify({
                            prompt: m.prompt || '',
                            negativePrompt: m.negativePrompt || '',
                            resolution: m.resolution || '',
                            seedUsed: m.seedUsed,
                            guidanceScale: m.guidanceScale
                        });
                    })()""",
                    lambda result, c=captured: self._parse_js_metadata(result, c),
                )

            download.isFinishedChanged.connect(
                lambda tp=temp_path, cap=captured: self._finalize_manual_download(
                    tp, cap
                )
            )

            download.accept()
            self._emit_status("Downloading image from Perchance\u2026")

        except Exception as e:
            self._emit_status(f"Download error: {e}")

    @staticmethod
    def _parse_js_metadata(result, target: dict):
        """Parse a JSON metadata string from JavaScript into *target* dict."""
        try:
            if result and result != "{}":
                target.update(json.loads(result))
        except (json.JSONDecodeError, TypeError):
            pass

    def _finalize_manual_download(self, temp_path: Path, captured: dict):
        """
        Post-process a completed manual download: read the temp file, save
        as JPEG with full EXIF metadata via the shared ``_save_image`` path,
        and clean up the temporary file.
        """
        if not temp_path.exists():
            return
        try:
            if temp_path.stat().st_size == 0:
                temp_path.unlink(missing_ok=True)
                return
        except OSError:
            return

        try:
            image_bytes = temp_path.read_bytes()
        except OSError:
            return

        path = self._save_image(
            image_bytes=image_bytes,
            prompt=captured.get("prompt", ""),
            negative_prompt=captured.get("negativePrompt", ""),
            resolution=captured.get("resolution", ""),
            seed=captured.get("seedUsed", -1),
            guidance_scale=captured.get("guidanceScale"),
        )

        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

        if path:
            self._emit_status(f"Image saved: {Path(path).name}")

    # ── Ad-hide JavaScript (Layer 2) ────────────────────────────────────

    def get_ad_hide_script(self) -> str:
        """
        Return JavaScript that hides ad-related DOM elements, the navigation
        menu bar, and zeroes ``--menu-bar-height`` to prevent invisible layout
        gaps.  A MutationObserver watches for dynamically inserted nodes.
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
        try {{
            document.documentElement.style.setProperty('--menu-bar-height', '0px');
        }} catch(e) {{}}
    }}

    hide();
    setTimeout(hide, 500);
    setTimeout(hide, 1500);
    setTimeout(hide, 4000);

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

    # ── Auto-download injection script ──────────────────────────────────

    def get_auto_download_script(self) -> str:
        """
        Return JavaScript that auto-captures generated images via postMessage
        interception.  Must be registered on the **profile** (not the page)
        with ``runsOnSubFrames=True`` and ``DocumentCreation`` timing so that
        dynamically created image-generation iframes receive the listener
        before they begin processing.

        * **Top frame**: maintains ``window._perchanceImageQueue`` (polled by
          Python via ``poll_image_queue``) and ``window._perchanceLastMeta``
          (read by the manual-download handler for EXIF metadata).
        * **Generator sub-frames**: listen for ``finished`` postMessages from
          ``image-generation.perchance.org`` iframes, extract metadata
          (prompt, negative, seed, resolution, guidance) from the iframe URL
          hash, and forward everything to ``window.top``.
        """
        return r"""
(function() {
    if (window._perchanceAutoDownloadActive) return;
    window._perchanceAutoDownloadActive = true;

    var isTopFrame = false;
    try { isTopFrame = (window === window.top); } catch(e) {}

    if (isTopFrame) {
        if (!window._perchanceImageQueue) window._perchanceImageQueue = [];
        window._perchanceLastMeta = null;

        window.addEventListener('message', function(event) {
            try {
                var d = event.data;
                if (d && d._perchanceAutoSave) {
                    window._perchanceImageQueue.push(d._perchanceAutoSave);
                    window._perchanceLastMeta = d._perchanceAutoSave;
                }
            } catch(e) {}
        });
    }

    if (!isTopFrame) {
        var processedIds = {};

        window.addEventListener('message', function(event) {
            try {
                var data = event.data;
                if (!data || data.type !== 'finished' || !data.dataUrl || !data.id) return;
                if (processedIds[data.id]) return;
                processedIds[data.id] = true;

                var meta = {};
                try {
                    var iframe = document.querySelector('iframe.' + CSS.escape(data.id));
                    if (iframe) {
                        var hashStr = (iframe.src || iframe.getAttribute('data-src') || '').split('#')[1] || '';
                        if (hashStr) meta = JSON.parse(decodeURIComponent(hashStr));
                    }
                } catch(e) {}

                window.top.postMessage({
                    _perchanceAutoSave: {
                        dataUrl: data.dataUrl,
                        seedUsed: data.seedUsed,
                        prompt: meta.prompt || '',
                        negativePrompt: meta.negativePrompt || '',
                        resolution: meta.resolution || '',
                        guidanceScale: meta.guidanceScale
                    }
                }, '*');
            } catch(e) {}
        });
    }
})();
"""

    # ── Queue polling (called from PerchancePage) ───────────────────────

    def poll_image_queue(self):
        """Run JavaScript to drain the image queue and process results."""
        if not self._page:
            return
        self._page.runJavaScript(
            """(function() {
                if (!window._perchanceImageQueue || !window._perchanceImageQueue.length)
                    return '[]';
                var items = window._perchanceImageQueue.splice(0);
                var result = [];
                for (var i = 0; i < items.length; i++) {
                    result.push({
                        dataUrl: items[i].dataUrl,
                        seedUsed: items[i].seedUsed,
                        prompt: items[i].prompt || '',
                        negativePrompt: items[i].negativePrompt || '',
                        resolution: items[i].resolution || '',
                        guidanceScale: items[i].guidanceScale
                    });
                }
                return JSON.stringify(result);
            })();""",
            self._process_queue_result,
        )

    def _process_queue_result(self, result):
        """Handle the JSON string returned by the queue-polling JavaScript."""
        if not result or result == "[]":
            return

        try:
            items = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return

        saved_count = 0
        for item in items:
            try:
                data_url = item.get("dataUrl", "")
                if not data_url or "," not in data_url:
                    continue

                raw_b64 = data_url.split(",", 1)[1]
                image_bytes = base64.b64decode(raw_b64)
                if len(image_bytes) < 1000:
                    continue

                path = self._save_image(
                    image_bytes=image_bytes,
                    prompt=item.get("prompt", ""),
                    negative_prompt=item.get("negativePrompt", ""),
                    resolution=item.get("resolution", ""),
                    seed=item.get("seedUsed", -1),
                    guidance_scale=item.get("guidanceScale"),
                )
                if path:
                    saved_count += 1
            except Exception as e:
                self._emit_status(f"Auto-save error: {e}")

        if saved_count:
            label = "image" if saved_count == 1 else "images"
            self._emit_status(f"Auto-saved {saved_count} Perchance {label}")

    # ── Image saving with EXIF ──────────────────────────────────────────

    def _save_image(
        self,
        image_bytes: bytes,
        prompt: str = "",
        negative_prompt: str = "",
        resolution: str = "",
        seed=-1,
        guidance_scale=None,
    ) -> Optional[str]:
        """
        Save image bytes as a JPEG with comprehensive EXIF metadata.

        The pipe-delimited metadata string format matches the project
        convention used by ``save_generated_image`` in ``core/utils.py``
        so the gallery service can parse all fields uniformly.

        Returns the saved file path, or ``None`` on failure.
        """
        images_dir = Path("images")
        images_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        final_path = images_dir / f"{timestamp}.jpg"
        counter = 1
        while final_path.exists():
            final_path = images_dir / f"{timestamp}_{counter}.jpg"
            counter += 1

        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))

            # Use actual pixel dimensions when the metadata lacks resolution
            actual_size = resolution or f"{img.width}x{img.height}"

            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            # Build pipe-delimited metadata (matches gallery_service parser)
            parts = []
            if prompt:
                parts.append(f"Prompt: {prompt}")
            if negative_prompt:
                parts.append(f"Negative: {negative_prompt}")
            parts.append(f"Size: {actual_size}")
            parts.append(f"Seed: {seed}")
            if guidance_scale is not None:
                parts.append(f"GuidanceScale: {guidance_scale}")
            parts.append("Service: Perchance")
            metadata_str = " | ".join(parts)

            exif = img.getexif()
            exif[0x010E] = metadata_str  # ImageDescription
            exif[0x0131] = "Perchance AI"  # Software
            img.save(str(final_path), "JPEG", quality=95, exif=exif.tobytes())
            return str(final_path)

        except ImportError:
            pass
        except Exception as e:
            self._emit_status(f"Image conversion note: {e}")

        # Fallback: write raw bytes when Pillow is unavailable
        try:
            with open(final_path, "wb") as f:
                f.write(image_bytes)
            return str(final_path)
        except OSError:
            return None

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