# core/services/gallery_service.py
"""
Gallery Service - Reads and caches image metadata from the generated images directory.

Separates *scanning* (filesystem I/O) from *filtering* (in-memory) so that
search / filter / favorites operations never touch the disk.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict
import json


@dataclass
class ImageMetadata:
    filepath: str
    prompt: str
    service: str
    model: str
    timestamp: str
    negative_prompt: str = ""
    size: str = ""
    seed: str = ""
    guidance_scale: str = ""
    is_favorite: bool = False


class GalleryService:
    def __init__(self):
        self._cache: Dict[str, tuple] = {}          # filepath -> (mtime, ImageMetadata)
        self._all_images: List[ImageMetadata] = []   # sorted master list (rebuilt on scan)
        self._scanned = False
        self.images_dir = Path("images")
        self.images_dir.mkdir(exist_ok=True)
        self.favorites_file = self.images_dir / "favorites.json"
        self._favorites: set = set()
        self._load_favorites()

    # ── Favorites persistence ───────────────────────────────────────────

    def _load_favorites(self):
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, 'r') as f:
                    self._favorites = set(json.load(f))
            except Exception:
                pass

    def _save_favorites(self):
        try:
            with open(self.favorites_file, 'w') as f:
                json.dump(list(self._favorites), f)
        except Exception:
            pass

    def toggle_favorite(self, filepath: str) -> bool:
        filename = Path(filepath).name
        if filename in self._favorites:
            self._favorites.remove(filename)
            is_fav = False
        else:
            self._favorites.add(filename)
            is_fav = True
        self._save_favorites()
        # Update cached metadata in-place (_all_images shares the same objects)
        if filepath in self._cache:
            self._cache[filepath][1].is_favorite = is_fav
        return is_fav

    def is_favorite(self, filepath: str) -> bool:
        return Path(filepath).name in self._favorites

    # ── Scanning (filesystem I/O) ───────────────────────────────────────

    def scan(self):
        """Re-scan the images directory for new / modified / deleted files.

        Only files whose mtime differs from the cached value are re-parsed.
        Call this when filesystem changes are expected (tab switch, after
        image generation, etc.).  Filter / search / favorites should use
        ``get_filtered()`` instead — no I/O required.
        """
        if not self.images_dir.exists():
            if self._cache:
                self._cache.clear()
                self._all_images.clear()
            self._scanned = True
            return

        current_files: set = set()
        changed = False

        for p in self.images_dir.glob("*.jpg"):
            filepath_str = str(p)
            current_files.add(filepath_str)
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue

            if filepath_str in self._cache and self._cache[filepath_str][0] == mtime:
                continue                                  # already cached & unchanged

            meta = self._parse_metadata(p)
            meta.is_favorite = self.is_favorite(filepath_str)
            self._cache[filepath_str] = (mtime, meta)
            changed = True

        # Purge entries for deleted files
        deleted = [fp for fp in self._cache if fp not in current_files]
        for fp in deleted:
            del self._cache[fp]
            changed = True

        # Rebuild the sorted master list only when something changed
        if changed or not self._scanned:
            self._all_images = [meta for _, meta in self._cache.values()]
            self._all_images.sort(key=lambda x: x.filepath, reverse=True)

        self._scanned = True

    # ── Filtering (in-memory, no I/O) ───────────────────────────────────

    def get_filtered(
        self,
        filter_service: str = "All",
        favorites_only: bool = False,
        search_query: str = "",
    ) -> List[ImageMetadata]:
        """Return images matching the given criteria from the cached list.

        This never touches the filesystem — call ``scan()`` first if the
        directory contents may have changed.
        """
        if not self._scanned:
            self.scan()

        result = self._all_images

        if filter_service != "All":
            fl = filter_service.lower()
            result = [m for m in result if m.service.lower() == fl]
        if favorites_only:
            result = [m for m in result if m.is_favorite]
        if search_query:
            q = search_query.lower()
            result = [m for m in result if q in m.prompt.lower()]

        return result

    def get_images(
        self,
        filter_service: str = "All",
        favorites_only: bool = False,
        search_query: str = "",
    ) -> List[ImageMetadata]:
        """Convenience: ``scan()`` + ``get_filtered()``."""
        self.scan()
        return self.get_filtered(filter_service, favorites_only, search_query)

    # ── Metadata parsing ────────────────────────────────────────────────

    def _parse_metadata(self, filepath: Path) -> ImageMetadata:
        prompt = ""
        service = "Unknown"
        model = "Unknown"
        timestamp = filepath.stem
        negative_prompt = ""
        size = ""
        seed = ""
        guidance_scale = ""

        try:
            from PIL import Image
            with Image.open(filepath) as img:
                exif = img.getexif()
                if exif and 0x010E in exif:
                    meta_str = exif[0x010E]
                    parts = [p.strip() for p in meta_str.split("|")]
                    for part in parts:
                        if part.startswith("Prompt:"):
                            prompt = part[7:].strip()
                        elif part.startswith("Service:"):
                            service = part[8:].strip()
                        elif part.startswith("Model:"):
                            model = part[6:].strip()
                        elif part.startswith("Negative:"):
                            negative_prompt = part[9:].strip()
                        elif part.startswith("Size:"):
                            size = part[5:].strip()
                        elif part.startswith("Seed:"):
                            seed = part[5:].strip()
                        elif part.startswith("GuidanceScale:"):
                            guidance_scale = part[14:].strip()
        except Exception:
            pass

        return ImageMetadata(
            str(filepath), prompt, service, model, timestamp,
            negative_prompt, size, seed, guidance_scale,
            is_favorite=self.is_favorite(str(filepath))
        )