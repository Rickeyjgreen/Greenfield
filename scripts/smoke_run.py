from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from photo_router.db import Database
from photo_router.exporter import export_package_with_summary
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
    (folder / 'IMG_0001_primary.JPG').write_bytes(b'primary-image')
    (folder / 'IMG_0002_alt.JPG').write_bytes(b'alt-image')
    (folder / 'IMG_0003_group.JPG').write_bytes(b'group-image')


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
        csv_path, json_path, routed_root, summary_json_path, summary_txt_path = export_package_with_summary(rows, export_root)

        assert len(roster.rows) == 2
        assert len(scans) == 1
        assert scans[0].matched is True
        assert len(rows) == 3
        assert rows[0]['class_label'] == 'student_solo_primary_candidate'
        assert rows[0]['selected_final'] == 1
        assert rows[1]['class_label'] == 'student_solo_alt_candidate'
        assert rows[2]['class_label'] == 'buddy_multi_person'
        assert csv_path.exists() and json_path.exists()
        assert summary_json_path.exists() and summary_txt_path.exists()
        assert (routed_root / 'student_solo_primary_candidate' / 'A123' / 'IMG_0001_primary.JPG').exists()
        assert (routed_root / 'student_solo_alt_candidate' / 'A123' / 'IMG_0002_alt.JPG').exists()
        assert (routed_root / 'buddy_multi_person' / 'A123' / 'IMG_0003_group.JPG').exists()

        summary_data = json.loads(summary_json_path.read_text(encoding='utf-8'))
        assert summary_data['total_rows'] == 3
        assert summary_data['copied_count'] == 3
        assert summary_data['missing_source_count'] == 0
        assert summary_data['failed_copy_count'] == 0
        assert summary_data['rows_by_class_label']['student_solo_primary_candidate'] == 1
        assert summary_data['rows_by_class_label']['student_solo_alt_candidate'] == 1
        assert summary_data['rows_by_class_label']['buddy_multi_person'] == 1
        db.close()
        print('SMOKE_OK')


if __name__ == '__main__':
    main()
