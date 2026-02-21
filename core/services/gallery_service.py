# core/services/gallery_service.py
"""
Gallery Service - Reads and caches image metadata from the generated images directory.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ImageMetadata:
    filepath: str
    prompt: str
    service: str
    model: str
    timestamp: str


class GalleryService:
    def __init__(self):
        self._cache: Dict[str, tuple[float, ImageMetadata]] = {}
        self.images_dir = Path("images")
        self.images_dir.mkdir(exist_ok=True)
        
    def get_images(self, filter_service: str = "All") -> List[ImageMetadata]:
        images = []
        if not self.images_dir.exists():
            return images
            
        for p in self.images_dir.glob("*.jpg"):
            try:
                mtime = p.stat().st_mtime
                filepath_str = str(p)
                
                # Check cache mapping via modified time
                if filepath_str in self._cache and self._cache[filepath_str][0] == mtime:
                    meta = self._cache[filepath_str][1]
                else:
                    meta = self._parse_metadata(p)
                    self._cache[filepath_str] = (mtime, meta)
                    
                if filter_service == "All" or meta.service.lower() == filter_service.lower():
                    images.append(meta)
            except Exception:
                continue
                
        # Sort by filepath descending (newest timestamp first)
        images.sort(key=lambda x: x.filepath, reverse=True)
        return images
        
    def _parse_metadata(self, filepath: Path) -> ImageMetadata:
        prompt = ""
        service = "Unknown"
        model = "Unknown"
        timestamp = filepath.stem
        
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
        except Exception:
            pass
            
        return ImageMetadata(str(filepath), prompt, service, model, timestamp)