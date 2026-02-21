# gui/widgets/media_panel.py
"""
Media Panel - Secondary pane for generative imaging interfacing.
Provides tabbed navigation for different image generation APIs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor


class MediaPanel(QWidget):
    """Secondary pane with tabbed navigation for image generation API interfaces."""

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._current_tab = 0
        self._tabs = []
        self._build_ui()

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

        for name in self.TAB_NAMES:
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
