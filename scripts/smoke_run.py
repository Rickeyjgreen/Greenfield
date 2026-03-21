from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from photo_router.db import Database
from photo_router.export_audit import export_job_package_with_audit, get_latest_export_audit_report
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
        csv_path, json_path, routed_root, summary_json_path, summary_txt_path, audit_id = export_job_package_with_audit(
            db,
            job_id,
            export_root,
        )
        latest_report = get_latest_export_audit_report(db, job_id)

        assert len(roster.rows) == 2
        assert len(scans) == 1
        assert scans[0].matched is True
        assert csv_path.exists() and json_path.exists()
        assert summary_json_path.exists() and summary_txt_path.exists()
        assert audit_id > 0
        assert latest_report is not None
        assert latest_report.job_id == job_id
        assert latest_report.total_rows == 3
        assert latest_report.copied_count == 3
        assert latest_report.missing_source_count == 0
        assert latest_report.failed_copy_count == 0
        assert Path(latest_report.output_path) == export_root
        assert Path(latest_report.routed_root_path) == routed_root
        assert Path(latest_report.summary_json_path) == summary_json_path
        assert Path(latest_report.summary_txt_path) == summary_txt_path
        assert latest_report.audit_id == audit_id
        assert (routed_root / 'student_solo_primary_candidate' / 'A123' / 'IMG_0001_primary.JPG').exists()
        assert (routed_root / 'student_solo_alt_candidate' / 'A123' / 'IMG_0002_alt.JPG').exists()
        assert (routed_root / 'buddy_multi_person' / 'A123' / 'IMG_0003_group.JPG').exists()
        db.close()
        print('SMOKE_OK')


if __name__ == '__main__':
    main()
