from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import IMAGE_EXTENSIONS
from .roster import LoadedRoster, RosterRow


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


def scan_image_root(root_path: str | Path, roster: LoadedRoster) -> list[FolderScan]:
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f'Image root not found: {root}')
    if not root.is_dir():
        raise NotADirectoryError(f'Image root is not a directory: {root}')

    roster_by_access_code = {row.access_code: row for row in roster.rows if row.access_code}

    scans: list[FolderScan] = []
    for folder in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda p: p.name.lower()):
        image_files = _iter_image_files(folder)
        images = [
            ScannedImage(
                order_index=index,
                filename=image_file.name,
                path=image_file,
                modified_time=image_file.stat().st_mtime,
            )
            for index, image_file in enumerate(image_files, start=1)
        ]
        folder_key = folder.name.strip()
        scans.append(
            FolderScan(
                folder_name=folder.name,
                folder_path=folder,
                folder_key=folder_key,
                roster_row=roster_by_access_code.get(folder_key),
                images=images,
            )
        )

    return scans
