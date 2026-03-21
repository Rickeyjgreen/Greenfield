from __future__ import annotations

import csv
import json
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
        export_rows = db.fetch_export_rows(job_id)
        alt_path = next(Path(row['file_path']) for row in export_rows if row['source_filename'] == 'IMG_0002_alt.JPG')
        group_path = next(Path(row['file_path']) for row in export_rows if row['source_filename'] == 'IMG_0003_group.JPG')
        db.connection.execute(
            "UPDATE images SET class_label = 'review_required', selected_final = 0 WHERE filename = ?",
            ('IMG_0002_alt.JPG',),
        )
        db.connection.execute(
            "UPDATE images SET class_label = 'reject', selected_final = 0 WHERE filename = ?",
            ('IMG_0003_group.JPG',),
        )
        db.connection.commit()

        csv_path, json_path, routed_root, summary_json_path, summary_txt_path, audit_id = export_job_package_with_audit(
            db,
            job_id,
            export_root,
        )
        latest_report = get_latest_export_audit_report(db, job_id)

        manifest_rows = json.loads(json_path.read_text(encoding='utf-8'))
        summary_data = json.loads(summary_json_path.read_text(encoding='utf-8'))

        assert len(roster.rows) == 2
        assert len(scans) == 1
        assert scans[0].matched is True
        assert csv_path.exists() and json_path.exists()
        assert summary_json_path.exists() and summary_txt_path.exists()
        assert audit_id > 0
        assert latest_report is not None
        assert len(manifest_rows) == 1
        assert manifest_rows[0]['source_filename'] == 'IMG_0001_primary.JPG'
        assert latest_report.job_id == job_id
        assert latest_report.total_rows == 1
        assert latest_report.copied_count == 1
        assert latest_report.missing_source_count == 0
        assert latest_report.failed_copy_count == 0
        assert latest_report.skipped_count == 2
        assert latest_report.skipped_by_class_label['review_required'] == 1
        assert latest_report.skipped_by_class_label['reject'] == 1
        assert latest_report.final_only is False
        assert 'review_required' not in latest_report.include_class_labels
        assert 'reject' not in latest_report.include_class_labels
        assert Path(latest_report.output_path) == export_root
        assert Path(latest_report.routed_root_path) == routed_root
        assert Path(latest_report.summary_json_path) == summary_json_path
        assert Path(latest_report.summary_txt_path) == summary_txt_path
        assert (routed_root / 'student_solo_primary_candidate' / 'A123' / 'IMG_0001_primary.JPG').exists()
        assert not (routed_root / 'review_required' / 'A123' / 'IMG_0002_alt.JPG').exists()
        assert not (routed_root / 'reject' / 'A123' / 'IMG_0003_group.JPG').exists()
        assert alt_path.exists()
        assert group_path.exists()
        assert summary_data['skipped_count'] == 2
        assert summary_data['skipped_by_class_label']['review_required'] == 1
        assert summary_data['skipped_by_class_label']['reject'] == 1
        db.close()
        print('SMOKE_OK')


if __name__ == '__main__':
    main()
