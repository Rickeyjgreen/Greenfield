from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .constants import IMAGE_EXTENSIONS
from .roster import LoadedRoster, RosterRow

TIFF_COPYRIGHT_TAG = 33432
UNMATCHED_ROOT_GROUP = '__UNMATCHED_ROOT__'


@dataclass(slots=True)
class ScannedImage:
    order_index: int
    filename: str
    path: Path
    modified_time: float


@dataclass(slots=True)
class FolderScan:
    folder_name: str
    folder_path: Path
    folder_key: str
    roster_row: RosterRow | None
    images: list[ScannedImage]

    @property
    def matched(self) -> bool:
        return self.roster_row is not None


def _iter_image_files(folder_path: Path) -> list[Path]:
    files = [
        item for item in folder_path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files, key=lambda item: (item.name.lower(), item.stat().st_mtime))


def _make_scanned_images(image_files: list[Path]) -> list[ScannedImage]:
    return [
        ScannedImage(
            order_index=index,
            filename=image_file.name,
            path=image_file,
            modified_time=image_file.stat().st_mtime,
        )
        for index, image_file in enumerate(image_files, start=1)
    ]


def _normalize_metadata_value(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        try:
            value = value.decode('utf-8', errors='ignore')
        except Exception:
            value = value.decode(errors='ignore')
    return str(value).strip()


def _extract_metadata_barcode(image_path: Path) -> str:
    try:
        with Image.open(image_path) as image:
            exif = image.getexif()
            if exif:
                barcode = _normalize_metadata_value(exif.get(TIFF_COPYRIGHT_TAG))
                if barcode:
                    return barcode

            tag_v2 = getattr(image, 'tag_v2', None)
            if tag_v2 is not None:
                barcode = _normalize_metadata_value(tag_v2.get(TIFF_COPYRIGHT_TAG))
                if barcode:
                    return barcode

            info = getattr(image, 'info', {}) or {}
            for key in ('copyright', 'Copyright', 'tiff:copyright'):
                barcode = _normalize_metadata_value(info.get(key))
                if barcode:
                    return barcode
    except Exception:
        return ''

    return ''


def _scan_folder_mode(root: Path, roster_by_access_code: dict[str, RosterRow]) -> list[FolderScan]:
    scans: list[FolderScan] = []
    for folder in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda p: p.name.lower()):
        image_files = _iter_image_files(folder)
        folder_key = folder.name.strip()
        scans.append(
            FolderScan(
                folder_name=folder.name,
                folder_path=folder,
                folder_key=folder_key,
                roster_row=roster_by_access_code.get(folder_key),
                images=_make_scanned_images(image_files),
            )
        )
    return scans


def _scan_flat_root_mode(root: Path, roster_by_barcode: dict[str, RosterRow]) -> list[FolderScan]:
    image_files = _iter_image_files(root)
    grouped_files: dict[str, list[Path]] = defaultdict(list)

    for image_file in image_files:
        barcode = _extract_metadata_barcode(image_file)
        group_key = barcode if barcode else UNMATCHED_ROOT_GROUP
        grouped_files[group_key].append(image_file)

    scans: list[FolderScan] = []
    for group_key in sorted(grouped_files, key=str.lower):
        group_files = sorted(grouped_files[group_key], key=lambda item: (item.name.lower(), item.stat().st_mtime))
        folder_name = group_key if group_key != UNMATCHED_ROOT_GROUP else f'{root.name}_{UNMATCHED_ROOT_GROUP}'
        scans.append(
            FolderScan(
                folder_name=folder_name,
                folder_path=root,
                folder_key=group_key,
                roster_row=roster_by_barcode.get(group_key),
                images=_make_scanned_images(group_files),
            )
        )
    return scans


def scan_image_root(root_path: str | Path, roster: LoadedRoster) -> list[FolderScan]:
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f'Image root not found: {root}')
    if not root.is_dir():
        raise NotADirectoryError(f'Image root is not a directory: {root}')

    roster_by_access_code = {row.access_code: row for row in roster.rows if row.access_code}
    roster_by_barcode = {row.barcode_raw: row for row in roster.rows if row.barcode_raw}

    folders = [item for item in root.iterdir() if item.is_dir()]
    if folders:
        return _scan_folder_mode(root, roster_by_access_code)

    return _scan_flat_root_mode(root, roster_by_barcode)
