# gui/widgets/gallery_page.py
"""
Gallery Page - Displays generated images in a responsive 4x3 grid.
Includes pagination, filtering, and prompt copying functionalities.
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QEvent
from PyQt6.QtGui import QCursor

from gui.widgets.image_gen_common import ImageDisplay, BTN_DROPDOWN, make_dropdown
from core.utils import reveal_file_in_explorer
from core.services.gallery_service import GalleryService


class ElidedLabel(QLabel):
    """A QLabel that elides its text on the right if it exceeds widget width."""
    clicked = pyqtSignal()
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        
    def setText(self, text):
        self._full_text = text
        super().setText(text)
        self.update_elision()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elision()
        
    def update_elision(self):
        fm = self.fontMetrics()
        w = max(0, self.width() - 2)
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, w)
        super().setText(elided)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class GalleryItemWidget(QWidget):
    """Individual container for an image, prompt, and metadata in the Gallery grid."""
    prompt_copied = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filepath = ""
        self.prompt = ""
        
        self.setStyleSheet("""
            GalleryItemWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        
        # Force uniform sizing and prevent layout collapse when hidden
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        self.image_display = ImageDisplay()
        self.image_display.setMinimumSize(32, 32)
        
        self.prompt_label = ElidedLabel()
        self.prompt_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prompt_label.setStyleSheet("color: #ccc; font-size: 11px; border: none; background: transparent;")
        self.prompt_label.setToolTip("Click to copy prompt")
        
        self.meta_label = ElidedLabel()
        self.meta_label.setStyleSheet("color: #888; font-size: 10px; border: none; background: transparent;")
        
        layout.addWidget(self.image_display, stretch=1)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.meta_label)
        
        self.image_display.clicked.connect(self._on_image_clicked)
        self.prompt_label.clicked.connect(self._on_prompt_clicked)
        
    def set_data(self, meta):
        self.filepath = meta.filepath
        self.prompt = meta.prompt
        self.image_display.set_image(meta.filepath)
        
        display_prompt = self.prompt.replace('\n', ' ').strip()
        if not display_prompt:
            display_prompt = "No prompt"
            
        self.prompt_label.setText(display_prompt)
        
        try:
            dt = datetime.strptime(meta.timestamp, "%Y-%m-%d_%H-%M-%S")
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts_str = meta.timestamp
            
        self.meta_label.setText(f"{meta.service} | {meta.model} | {ts_str}")
        self.show()
        
    def clear(self):
        self.filepath = ""
        self.prompt = ""
        self.image_display.clear_image()
        self.prompt_label.setText("")
        self.meta_label.setText("")
        self.hide()
        
    def _on_image_clicked(self):
        if self.filepath:
            reveal_file_in_explorer(self.filepath)
            
    def _on_prompt_clicked(self):
        if self.prompt:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.prompt)
            self.prompt_copied.emit("Prompt copied to clipboard.")


class GalleryPage(QWidget):
    """Media Gallery page displaying generated images in a paginated grid."""
    status_updated = pyqtSignal(str)
    
    FILTERS = ["All", "Pollinations", "Airforce", "Perchance"]
    ITEMS_PER_PAGE = 12

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.service = GalleryService()
        
        self.images = []
        self.current_page = 1
        self.total_pages = 1
        self.current_filter = "All"
        self._items = []
        
        self.active_dropdown = None
        self.hide_timer = QTimer()
        self.hide_timer.setInterval(250)
        self.hide_timer.timeout.connect(self._hide_dropdown)
        
        self._build_ui()
        self._load_from_config()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Controls Bar ---
        controls = QWidget()
        controls.setStyleSheet("background-color: #121212;")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(6)
        
        cl.addStretch(1)
        
        # Internal Page Pagination
        paginator_layout = QHBoxLayout()
        paginator_layout.setSpacing(2)
        
        self.first_btn = QPushButton("«")
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.last_btn = QPushButton("»")
        
        for btn in [self.first_btn, self.prev_btn, self.next_btn, self.last_btn]:
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(BTN_DROPDOWN)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            paginator_layout.addWidget(btn)
            
        self.first_btn.clicked.connect(lambda: self.set_page(1))
        self.prev_btn.clicked.connect(lambda: self.set_page(self.current_page - 1))
        self.next_btn.clicked.connect(lambda: self.set_page(self.current_page + 1))
        self.last_btn.clicked.connect(self._goto_last_page)
        
        self.page_label = QLabel("Page 1 of 1 (0 items)")
        self.page_label.setStyleSheet("color: #ccc; font-size: 11px; padding: 0 8px;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        paginator_layout.insertWidget(2, self.page_label)
        cl.addLayout(paginator_layout)
        
        cl.addStretch(1)
        
        # Display Filtering Toggles
        self.filter_btn = QPushButton(self.current_filter)
        self.filter_btn.setStyleSheet(BTN_DROPDOWN)
        self.filter_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.filter_btn.setMinimumWidth(100)
        
        self.filter_dropdown = make_dropdown(self, self.FILTERS, self._on_filter_selected, self)
        self.filter_btn.installEventFilter(self)
        
        cl.addWidget(self.filter_btn)
        layout.addWidget(controls)
        
        # --- Grid Area ---
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: #2a2a2a;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(8)
        
        for row in range(3):
            self.grid_layout.setRowStretch(row, 1)
            for col in range(4):
                if row == 0:
                    self.grid_layout.setColumnStretch(col, 1)
                item = GalleryItemWidget()
                item.prompt_copied.connect(self.status_updated.emit)
                self.grid_layout.addWidget(item, row, col)
                self._items.append(item)
                
        layout.addWidget(self.grid_container, stretch=1)

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.Enter:
            if obj == self.filter_btn:
                self._show_dropdown(self.filter_dropdown, self.filter_btn)
            elif obj == self.filter_dropdown:
                self.hide_timer.stop()
        elif et == QEvent.Type.Leave:
            if obj in (self.filter_btn, self.filter_dropdown):
                self.hide_timer.start()
        return super().eventFilter(obj, event)

    def _show_dropdown(self, dropdown, button):
        self.hide_timer.stop()
        if self.active_dropdown and self.active_dropdown is not dropdown:
            self.active_dropdown.hide()
        if self.active_dropdown is dropdown:
            return
        self.active_dropdown = dropdown
        pos = button.mapToGlobal(button.rect().bottomLeft())
        dropdown.move(pos.x(), pos.y() + 2)
        dropdown.show()
        dropdown.raise_()

    def _hide_dropdown(self):
        if self.active_dropdown:
            self.active_dropdown.hide()
            self.active_dropdown = None

    def _on_filter_selected(self, filter_name: str):
        self.current_filter = filter_name
        self.filter_btn.setText(filter_name)
        self._hide_dropdown()
        self.current_page = 1
        self._save_to_config()
        self.refresh()
        
    def _save_to_config(self):
        if not self.config_manager:
            return
        self.config_manager.gallery_page = self.current_page
        self.config_manager.gallery_filter = self.current_filter
        self.config_manager.save()
        
    def _load_from_config(self):
        if not self.config_manager:
            return
        self.current_page = getattr(self.config_manager, "gallery_page", 1)
        self.current_filter = getattr(self.config_manager, "gallery_filter", "All")
        if self.current_filter in self.FILTERS:
            self.filter_btn.setText(self.current_filter)

    def refresh(self):
        self.images = self.service.get_images(self.current_filter)
        self.total_pages = max(1, (len(self.images) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        self._update_display()
        
    def _goto_last_page(self):
        self.set_page(self.total_pages)

    def set_page(self, page: int):
        if 1 <= page <= self.total_pages and page != self.current_page:
            self.current_page = page
            self._save_to_config()
            self._update_display()

    def _update_display(self):
        start_idx = (self.current_page - 1) * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_images = self.images[start_idx:end_idx]
        
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages} ({len(self.images)} items)")
        
        self.first_btn.setEnabled(self.current_page > 1)
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
        self.last_btn.setEnabled(self.current_page < self.total_pages)
        
        for i, item_widget in enumerate(self._items):
            if i < len(page_images):
                item_widget.set_data(page_images[i])
            else:
                item_widget.clear()

    def hideEvent(self, event):
        self._hide_dropdown()
        super().hideEvent(event)