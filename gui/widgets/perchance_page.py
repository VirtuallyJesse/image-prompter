# gui/widgets/perchance_page.py
"""
Perchance Page – Embeds a Perchance image generator in a QWebEngineView
with ad-blocking, auto-download, and persistent login / cookie storage.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from core.services.perchance_service import PerchanceService, is_webengine_available

PERCHANCE_URL = "https://perchance.org/a1481832-0a06-414f-baa6-616052e5f61d"


class PerchancePage(QWidget):
    """
    Perchance image generation page.

    Loads the Perchance generator URL inside a QWebEngineView with:

    * Persistent cookie / login profile
    * Two-layer ad blocking (request interception + DOM hiding)
    * Menu bar hiding (``#menuBarEl``, ``--menu-bar-height``)
    * Automatic image capture via postMessage interception
    * Full EXIF metadata embedding (prompt, negative, size, seed, guidance)
    * Manual download fallback with metadata from auto-download state

    Falls back to a static placeholder when PyQt6-WebEngine is not installed.
    """

    status_updated = pyqtSignal(str)

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.service = PerchanceService(config_manager)
        self.service.set_status_callback(self.status_updated.emit)

        self._webview = None
        self._page = None
        self._url_loaded = False
        self._poll_timer = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not is_webengine_available():
            self._build_fallback(layout)
            return

        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineScript

            # Persistent profile (cookies, ad-blocking, download handling)
            profile = self.service.create_profile(self)
            if not profile:
                self._build_fallback(layout)
                return

            self._webview = QWebEngineView()
            self._page = QWebEnginePage(profile, self._webview)
            self._webview.setPage(self._page)
            self.service.set_page(self._page)

            # Inject auto-download script at PROFILE level with DocumentCreation
            # timing.  This ensures every dynamically-created sub-frame
            # (including image-generation.perchance.org iframes) receives the
            # postMessage listener before any content executes.
            script = QWebEngineScript()
            script.setName("perchance_auto_download")
            script.setSourceCode(self.service.get_auto_download_script())
            script.setInjectionPoint(
                QWebEngineScript.InjectionPoint.DocumentCreation
            )
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setRunsOnSubFrames(True)
            profile.scripts().insert(script)

            # Ad-hide + menu-bar-hide after page load
            self._webview.loadFinished.connect(self._on_load_finished)

            # Poll timer drains the auto-download queue every second
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(1000)
            self._poll_timer.timeout.connect(self._poll_images)

            layout.addWidget(self._webview, 1)

        except Exception as e:
            self._build_fallback(layout, str(e))

    def _build_fallback(self, layout, error_msg=None):
        """Display an informational placeholder when WebEngine is unavailable."""
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("\U0001f3b2")  # 🎲
        icon.setStyleSheet("font-size: 32pt;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(icon)

        title = QLabel("Perchance")
        title.setStyleSheet("color: #666; font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        lines = ["PyQt6-WebEngine is required for Perchance integration."]
        if error_msg:
            lines.append(f"\n{error_msg}")
        lines.append("\nInstall:  pip install PyQt6-WebEngine")
        lines.append(f"\nOr visit directly:\n{PERCHANCE_URL}")

        desc = QLabel("\n".join(lines))
        desc.setStyleSheet("color: #888; font-size: 9pt;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(desc)

        layout.addWidget(container)

    # ── Events ──────────────────────────────────────────────────────────

    def showEvent(self, event):
        """Lazy-load the URL on first show to avoid heavy init at startup."""
        super().showEvent(event)
        if self._webview and not self._url_loaded:
            self._url_loaded = True
            from PyQt6.QtCore import QUrl

            url = PERCHANCE_URL
            if self.config_manager:
                url = getattr(self.config_manager, "perchance_url", url) or url
            self._webview.setUrl(QUrl(url))

    def _on_load_finished(self, ok: bool):
        """Inject ad-hiding CSS overrides and start the poll timer."""
        if not ok or not self._page:
            return

        script = self.service.get_ad_hide_script()
        if script:
            self._page.runJavaScript(script)

        if self._poll_timer and not self._poll_timer.isActive():
            self._poll_timer.start()

    # ── Auto-download polling ───────────────────────────────────────────

    def _poll_images(self):
        """Drain the auto-download queue via the service."""
        if self._page:
            self.service.poll_image_queue()