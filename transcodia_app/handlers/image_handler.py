"""
Image Conversion and Transformation Handler.
Batch conversion supporting WebP, JPG, PNG, ICO, BMP, GIF, TIFF.
"""

import os
from dataclasses import dataclass, replace
from typing import Optional, Tuple
from PIL import Image, ImageOps


@dataclass
class ImageConfig:
    quality: int = 85
    width: Optional[int] = None
    height: Optional[int] = None
    keep_aspect_ratio: bool = True
    rotate_angle: int = 0  # 0, 90, 180, 270
    flip_h: bool = False
    flip_v: bool = False


class ImageConverter:
    """Performs image format conversions and transformations."""

    @staticmethod
    def convert_image(src_path: str, dst_path: str, config: Optional[ImageConfig] = None) -> bool:
        cfg = replace(config) if config else ImageConfig()
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)
            # Handle RGBA to RGB for JPEG
            ext = os.path.splitext(dst_path)[1].lower()
            if ext in [".jpg", ".jpeg", ".bmp"] and img.mode in ("RGBA", "LA", "P"):
                # Create white background
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[3] if len(img.split()) >= 4 else None)
                img = bg
            elif ext == ".ico":
                # Rescale for icon if needed
                img = img.convert("RGBA")
                if not (cfg.width and cfg.height):
                    cfg.width, cfg.height = 256, 256

            # Transformations: Rotate & Flip
            if cfg.rotate_angle == 90:
                img = img.transpose(Image.Transpose.ROTATE_270)  # Clockwise 90
            elif cfg.rotate_angle == 180:
                img = img.transpose(Image.Transpose.ROTATE_180)
            elif cfg.rotate_angle == 270:
                img = img.transpose(Image.Transpose.ROTATE_90)

            if cfg.flip_h:
                img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if cfg.flip_v:
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Resize
            if cfg.width and cfg.height:
                if cfg.keep_aspect_ratio:
                    img.thumbnail((cfg.width, cfg.height), Image.Resampling.LANCZOS)
                else:
                    img = img.resize((cfg.width, cfg.height), Image.Resampling.LANCZOS)

            os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)

            # Save according to target extension
            if ext in [".jpg", ".jpeg"]:
                img.save(dst_path, "JPEG", quality=cfg.quality, optimize=True)
            elif ext == ".webp":
                img.save(dst_path, "WEBP", quality=cfg.quality)
            elif ext == ".png":
                img.save(dst_path, "PNG", optimize=True)
            elif ext == ".ico":
                img.save(dst_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            elif ext == ".bmp":
                img.save(dst_path, "BMP")
            elif ext == ".gif":
                img.save(dst_path, "GIF")
            elif ext in [".tif", ".tiff"]:
                img.save(dst_path, "TIFF")
            else:
                img.save(dst_path)

        return True
