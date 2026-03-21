from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from photo_router.db import Database
from photo_router.exporter import export_manifest
from photo_router.roster import load_roster
from photo_router.scanner import scan_image_root


ROSTER_HEADER = [
    'Child ID',
    'Student firstname',
    'Student lastname',
    'Group',
    'Access Code (1)',
    'Barcode (1)',
]


def write_sample_csv(path: Path) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(ROSTER_HEADER)
        writer.writerow(['1001', 'Rickey', 'Green', 'Team A', 'A123', '000123'])
        writer.writerow(['1002', 'Jane', 'Coach', 'Team A', 'A124', '000124'])


def write_sample_images(root: Path) -> None:
    folder = root / 'A123'
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        (folder / f'IMG_{index:04d}.JPG').write_bytes(b'not-a-real-image-yet')


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        roster_path = tmp / 'Ready_sample.csv'
        image_root = tmp / 'images'
        export_root = tmp / 'exports'
        image_root.mkdir(parents=True, exist_ok=True)

        write_sample_csv(roster_path)
        write_sample_images(image_root)

        roster = load_roster(roster_path)
        scans = scan_image_root(image_root, roster)

        db = Database(tmp / 'smoke.db')
        job_id = db.create_job(roster, image_root, scans)
        rows = db.fetch_export_rows(job_id)
        csv_path, json_path = export_manifest(rows, export_root)

        assert len(roster.rows) == 2
        assert len(scans) == 1
        assert scans[0].matched is True
        assert len(rows) == 3
        assert csv_path.exists() and json_path.exists()
        db.close()
        print('SMOKE_OK')


if __name__ == '__main__':
    main()
