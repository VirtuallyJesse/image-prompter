# gui/main_window.py
"""
Main Window GUI - Constructs the main application window with a split-pane layout.
Primary chat pane (left) with scoped footer, secondary media pane (right) with tabs.
"""
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QSplitter
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from gui.widgets.action_buttons_panel import ActionButtonsPanel
from gui.widgets.input_panel import InputPanel
from gui.widgets.response_panel import ResponsePanel
from gui.widgets.media_panel import MediaPanel


class MainWindow(QMainWindow):
    """Main application window with asymmetrical split-pane layout."""

    status_signal = pyqtSignal(str)

    def __init__(self, file_service):
        super().__init__()
        self.file_service = file_service
        self.file_service.files_updated.connect(self._on_files_updated)
        self.file_service.status_updated.connect(self.status_signal.emit)
        self.file_service.files_cleared.connect(self._on_files_cleared)
        self.setWindowTitle("PyQt6 Chat Framework")
        self.setWindowIcon(QIcon("assets/icons/app_icon.ico"))
        self.setStyleSheet("""
            QMainWindow, QStatusBar { background-color: #1a1a1a; }
            QLabel { color: #ffffff; font-family: Arial; }
            QPushButton { background-color: #3d3d3d; color: #ffffff; border: 1px solid #333; padding: 8px; font-family: Arial; font-size: 9pt; border-radius: 4px; }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QTextEdit { background-color: #1e1e1e; color: #ffffff; border: 1px solid #333; font-family: Consolas; font-size: 9pt; }
            QStatusBar { color: #888888; font-size: 8pt; }
            QSplitter::handle {
                background-color: #333333;
            }
            QSplitter::handle:hover {
                background-color: #4d4d4d;
            }
            QSplitter::handle:pressed {
                background-color: #1E88E5;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 5)
        main_layout.setSpacing(5)

        # --- Horizontal splitter: chat pane | media pane ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(5)
        self.splitter.setChildrenCollapsible(False)

        # Left pane: Chat (response + input + action buttons)
        chat_pane = QWidget()
        chat_pane.setMinimumWidth(400)
        chat_pane_layout = QVBoxLayout(chat_pane)
        chat_pane_layout.setContentsMargins(0, 0, 0, 0)
        chat_pane_layout.setSpacing(10)
        self._build_chat_pane(chat_pane_layout)
        self.splitter.addWidget(chat_pane)

        # Right pane: Media (tabbed image generation interface)
        self.media_panel = MediaPanel()
        self.media_panel.setMinimumWidth(280)
        self.splitter.addWidget(self.media_panel)

        # Default asymmetric split ~65/35, stretch ratio 3:2
        self.splitter.setSizes([780, 420])
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self.splitter, 1)

        # --- Status bar ---
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 8pt;")
        self.status_signal.connect(self.status_label.setText)
        main_layout.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignLeft)

        self.status_signal.emit("Ready")
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Set up global keyboard shortcuts."""
        search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        search_shortcut.activated.connect(self.response_panel.show_search)

        nav_left_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        nav_left_shortcut.activated.connect(lambda: self.action_buttons_panel.navigate_left_signal.emit())

        nav_right_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        nav_right_shortcut.activated.connect(lambda: self.action_buttons_panel.navigate_right_signal.emit())

        delete_all_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        delete_all_shortcut.activated.connect(lambda: self.action_buttons_panel.delete_all_chats_signal.emit())

    def _build_chat_pane(self, layout):
        """Build the primary chat pane with response, input, and action buttons."""
        self.main_panel_layout = layout

        # Response panel (takes all available vertical space)
        self.response_panel = ResponsePanel()
        layout.addWidget(self.response_panel)

        # Input panel (scoped footer - dynamic height)
        self.input_panel = InputPanel()
        layout.addWidget(self.input_panel)

        # Action buttons panel (scoped footer - fixed height)
        self.action_buttons_panel = ActionButtonsPanel(self.file_service)
        layout.addWidget(self.action_buttons_panel)

        self.input_panel.text_content_changed_signal.connect(self.action_buttons_panel.update_text_action_buttons)

        layout.setStretchFactor(self.response_panel, 1)
        layout.setStretchFactor(self.input_panel, 0)
        layout.setStretchFactor(self.action_buttons_panel, 0)

    def _on_files_cleared(self):
        self.action_buttons_panel.select_file_signal.emit("", "")

    def _on_files_updated(self, filenames):
        """Handle files updated signal - update status bar with file list."""
        if not filenames:
            self.status_signal.emit("No files selected.")
            return
        if len(filenames) == 1:
            self.status_signal.emit(f"File ready: {filenames[0]}")
        elif len(filenames) <= 3:
            self.status_signal.emit(f"Files ready: {', '.join(filenames)}")
        else:
            self.status_signal.emit(f"Files ready: {', '.join(filenames[:3])}... ({len(filenames)} total)")

    def keyPressEvent(self, event):
        """Handle keyboard events - Ctrl+V for clipboard paste."""
        modifiers = event.modifiers()
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            if mime_data.hasImage():
                img = clipboard.image()
                if not img.isNull():
                    from PyQt6.QtCore import QBuffer, QIODevice
                    buf = QBuffer()
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    img.save(buf, "PNG")
                    self.file_service.load_file_from_data(bytes(buf.data()), "clipboard.png")
                    return
        super().keyPressEvent(event)

    def get_input_text(self) -> str:
        """Get the text from the input text edit."""
        return self.input_panel.get_input_text()

    def closeEvent(self, event):
        """Handle window close event to save window size and splitter state."""
        if getattr(self, 'config_manager', None):
            self.config_manager.window_width = self.width()
            self.config_manager.window_height = self.height()
            self.config_manager.splitter_sizes = self.splitter.sizes()
            self.config_manager.save()
        event.accept()
