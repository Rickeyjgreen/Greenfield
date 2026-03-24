from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image

from .constants import IMAGE_EXTENSIONS
from .roster import LoadedRoster, RosterRow

TIFF_IMAGE_DESCRIPTION_TAG = 270
TIFF_COPYRIGHT_TAG = 33432
EXIF_XP_TITLE_TAG = 40091
UNMATCHED_ROOT_GROUP = '__UNMATCHED_ROOT__'
XMP_NAMESPACES = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
}


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
    source_barcode_raw: str = ''
    source_group_name: str = ''

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
    return str(value).strip().strip('\x00')


def _normalize_title_value(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        if b'\x00' in value:
            try:
                decoded = value.decode('utf-16-le', errors='ignore')
                return decoded.strip().strip('\x00')
            except Exception:
                pass
    return _normalize_metadata_value(value)


def _normalize_barcode_token(value: str) -> str:
    token = value.strip().strip('"\'[]()')
    token = re.sub(r'\s+', '', token)
    return token


def _barcode_candidates(raw_barcode: str) -> list[str]:
    cleaned = _normalize_metadata_value(raw_barcode)
    if not cleaned:
        return []
    candidates: list[str] = []
    for part in re.split(r'[;,\n\r]+', cleaned):
        token = _normalize_barcode_token(part)
        if token and token not in candidates:
            candidates.append(token)
    if not candidates:
        token = _normalize_barcode_token(cleaned)
        if token:
            candidates.append(token)
    return candidates


def _xmp_alt_text(root: ET.Element, tag_name: str) -> str:
    path = f'.//dc:{tag_name}/rdf:Alt/rdf:li'
    for node in root.findall(path, XMP_NAMESPACES):
        text = _normalize_metadata_value(node.text)
        if text:
            return text
    return ''


def _extract_xmp_fields(xmp_value: object) -> tuple[str, str]:
    text = _normalize_metadata_value(xmp_value)
    if not text:
        return '', ''
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return '', ''

    raw_barcode = _xmp_alt_text(root, 'rights')
    title = _xmp_alt_text(root, 'title')
    return raw_barcode, title


def _extract_metadata_fields(image_path: Path) -> tuple[str, str]:
    try:
        with Image.open(image_path) as image:
            raw_barcode = ''
            title = ''

            exif = image.getexif()
            if exif:
                raw_barcode = raw_barcode or _normalize_metadata_value(exif.get(TIFF_COPYRIGHT_TAG))
                title = title or _normalize_title_value(exif.get(TIFF_IMAGE_DESCRIPTION_TAG))
                title = title or _normalize_title_value(exif.get(EXIF_XP_TITLE_TAG))

            tag_v2 = getattr(image, 'tag_v2', None)
            if tag_v2 is not None:
                raw_barcode = raw_barcode or _normalize_metadata_value(tag_v2.get(TIFF_COPYRIGHT_TAG))
                title = title or _normalize_title_value(tag_v2.get(TIFF_IMAGE_DESCRIPTION_TAG))
                title = title or _normalize_title_value(tag_v2.get(EXIF_XP_TITLE_TAG))

            info = getattr(image, 'info', {}) or {}
            for key in ('copyright', 'Copyright', 'tiff:copyright'):
                raw_barcode = raw_barcode or _normalize_metadata_value(info.get(key))
            for key in ('title', 'Title', 'ImageDescription'):
                title = title or _normalize_title_value(info.get(key))

            xmp_value = info.get('xmp') or (exif.get(700) if exif else None)
            xmp_barcode, xmp_title = _extract_xmp_fields(xmp_value)
            raw_barcode = raw_barcode or xmp_barcode
            title = title or xmp_title

            return raw_barcode, title
    except Exception:
        return '', ''


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
    group_metadata: dict[str, dict[str, str]] = {}

    for image_file in image_files:
        raw_barcode, title = _extract_metadata_fields(image_file)
        candidates = _barcode_candidates(raw_barcode)
        matched_barcode = next((candidate for candidate in candidates if candidate in roster_by_barcode), '')
        group_key = matched_barcode or (candidates[0] if candidates else UNMATCHED_ROOT_GROUP)
        grouped_files[group_key].append(image_file)
        metadata = group_metadata.setdefault(group_key, {'barcode_raw': '', 'group_name': ''})
        if raw_barcode and not metadata['barcode_raw']:
            metadata['barcode_raw'] = raw_barcode
        if title and not metadata['group_name']:
            metadata['group_name'] = title

    scans: list[FolderScan] = []
    for group_key in sorted(grouped_files, key=str.lower):
        group_files = sorted(grouped_files[group_key], key=lambda item: (item.name.lower(), item.stat().st_mtime))
        metadata = group_metadata.get(group_key, {})
        scans.append(
            FolderScan(
                folder_name=root.name,
                folder_path=root,
                folder_key=group_key,
                roster_row=roster_by_barcode.get(group_key),
                images=_make_scanned_images(group_files),
                source_barcode_raw=metadata.get('barcode_raw', ''),
                source_group_name=metadata.get('group_name', ''),
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
