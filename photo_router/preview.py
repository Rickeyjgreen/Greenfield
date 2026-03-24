from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PySide6.QtGui import QImage, QPixmap


def load_preview_image(
    image_path: str | Path,
    max_width: int = 640,
    max_height: int = 480,
) -> tuple[QImage | None, str | None]:
    path = Path(image_path)
    if not path.exists():
        return None, f'Preview image not found: {path}'

    try:
        with Image.open(path) as image:
            image.thumbnail((max_width, max_height))
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGBA')

            if image.mode == 'RGBA':
                fmt = QImage.Format_RGBA8888
                bytes_per_line = image.width * 4
            else:
                fmt = QImage.Format_RGB888
                bytes_per_line = image.width * 3

            qimage = QImage(
                image.tobytes('raw', image.mode),
                image.width,
                image.height,
                bytes_per_line,
                fmt,
            ).copy()
            return qimage, None
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return None, f'Preview unavailable: {exc}'


def load_preview_pixmap(
    image_path: str | Path,
    max_width: int = 640,
    max_height: int = 480,
) -> tuple[QPixmap | None, str | None]:
    qimage, error = load_preview_image(image_path, max_width=max_width, max_height=max_height)
    if qimage is None:
        return None, error
    return QPixmap.fromImage(qimage), None
