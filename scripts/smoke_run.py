from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from PIL import Image, TiffImagePlugin

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
        writer.writerow(['1001', 'Rickey', 'Green', 'Roster Team A', 'A123', '31756845281541'])
        writer.writerow(['1002', 'Jane', 'Coach', 'Roster Team B', 'A124', '31756845281542'])


def write_sample_images(root: Path) -> None:
    matched_primary = root / 'IMG_0001_primary.tif'
    matched_alt = root / 'IMG_0002_alt.tif'
    unmatched = root / 'IMG_0003_unmatched.tif'

    image = Image.new('RGB', (8, 8), color='white')
    matched_info = TiffImagePlugin.ImageFileDirectory_v2()
    matched_info[33432] = '31756845281541'
    matched_info[270] = 'Image Title Team A'
    image.save(matched_primary, tiffinfo=matched_info)
    image.save(matched_alt, tiffinfo=matched_info)
    image.save(unmatched)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        roster_path = tmp / 'Ready_sample.csv'
        image_root = tmp / 'sm tif - Test Dupe'
        export_root = tmp / 'exports'
        image_root.mkdir(parents=True, exist_ok=True)

        write_sample_csv(roster_path)
        write_sample_images(image_root)

        roster = load_roster(roster_path)
        scans = scan_image_root(image_root, roster)

        db = Database(tmp / 'smoke.db')
        job_id = db.create_job(roster, image_root, scans)
        export_rows = db.fetch_export_rows(job_id)
        unmatched_path = next(Path(row['file_path']) for row in export_rows if row['source_filename'] == 'IMG_0003_unmatched.tif')
        db.connection.execute(
            "UPDATE images SET class_label = 'review_required', selected_final = 0 WHERE filename = ?",
            ('IMG_0003_unmatched.tif',),
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
        assert len(scans) == 2
        assert any(scan.matched for scan in scans)
        assert csv_path.exists() and json_path.exists()
        assert summary_json_path.exists() and summary_txt_path.exists()
        assert audit_id > 0
        assert latest_report is not None
        assert len(manifest_rows) == 2
        for row in manifest_rows:
            assert row['source_folder'] == 'sm tif - Test Dupe'
            assert row['group_name'] == 'Image Title Team A'
            assert row['child_id'] == '1001'
            assert row['access_code'] == 'A123'
            assert row['barcode_raw'] == '31756845281541'
        assert latest_report.job_id == job_id
        assert latest_report.total_rows == 2
        assert latest_report.copied_count == 2
        assert latest_report.missing_source_count == 0
        assert latest_report.failed_copy_count == 0
        assert latest_report.skipped_count == 1
        assert latest_report.skipped_by_class_label['review_required'] == 1
        assert latest_report.final_only is False
        assert 'review_required' not in latest_report.include_class_labels
        assert Path(latest_report.output_path) == export_root
        assert Path(latest_report.routed_root_path) == routed_root
        assert Path(latest_report.summary_json_path) == summary_json_path
        assert Path(latest_report.summary_txt_path) == summary_txt_path
        assert (routed_root / 'student_solo_primary_candidate' / 'sm_tif_-_Test_Dupe' / 'IMG_0001_primary.tif').exists()
        assert (routed_root / 'student_solo_alt_candidate' / 'sm_tif_-_Test_Dupe' / 'IMG_0002_alt.tif').exists()
        assert not (routed_root / 'review_required' / 'sm_tif_-_Test_Dupe' / 'IMG_0003_unmatched.tif').exists()
        assert unmatched_path.exists()
        assert summary_data['skipped_count'] == 1
        assert summary_data['skipped_by_class_label']['review_required'] == 1
        db.close()
        print('SMOKE_OK')


if __name__ == '__main__':
    main()
