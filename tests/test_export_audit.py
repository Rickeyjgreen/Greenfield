from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from photo_router.db import Database
from photo_router.export_audit import (
    export_job_package_with_audit,
    export_job_package_with_policy_and_audit,
    get_latest_export_audit_report,
)
from photo_router.exporter import DEFAULT_EXPORT_POLICY, ExportPolicy
from photo_router.roster import load_roster
from photo_router.scanner import scan_image_root


class ExportAuditTests(unittest.TestCase):
    def test_record_and_fetch_latest_export_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            roster_path = tmp / 'ready.csv'
            image_root = tmp / 'images'
            export_root = tmp / 'exports'
            image_root.mkdir(parents=True)
            folder = image_root / 'A123'
            folder.mkdir()
            (folder / 'IMG_0001_primary.JPG').write_bytes(b'primary')
            (folder / 'IMG_0002_alt.JPG').write_bytes(b'alt')

            with roster_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    'Child ID',
                    'Student firstname',
                    'Student lastname',
                    'Group',
                    'Access Code (1)',
                    'Barcode (1)',
                ])
                writer.writerow(['1', 'Rickey', 'Green', 'Team A', 'A123', '000123'])

            roster = load_roster(roster_path)
            scans = scan_image_root(image_root, roster)

            db = Database(tmp / 'audit.db')
            job_id = db.create_job(roster, image_root, scans)
            csv_path, json_path, routed_root, summary_json_path, summary_txt_path, audit_id = export_job_package_with_audit(
                db,
                job_id,
                export_root,
            )

            latest = db.fetch_latest_export_audit(job_id)
            latest_report = get_latest_export_audit_report(db, job_id)

            self.assertGreater(audit_id, 0)
            self.assertIsNotNone(latest)
            self.assertIsNotNone(latest_report)
            assert latest is not None
            assert latest_report is not None
            self.assertEqual(latest['job_id'], job_id)
            self.assertEqual(latest['output_path'], str(export_root))
            self.assertEqual(latest['routed_root_path'], str(routed_root))
            self.assertEqual(latest['summary_json_path'], str(summary_json_path))
            self.assertEqual(latest['summary_txt_path'], str(summary_txt_path))
            self.assertEqual(latest['total_rows'], 2)
            self.assertEqual(latest['copied_count'], 2)
            self.assertEqual(latest['missing_source_count'], 0)
            self.assertEqual(latest['failed_copy_count'], 0)
            self.assertEqual(latest['include_class_labels'], list(DEFAULT_EXPORT_POLICY.include_class_labels))
            self.assertFalse(latest['final_only'])
            self.assertEqual(latest['skipped_count'], 0)
            self.assertEqual(latest['skipped_by_class_label'], {})
            self.assertEqual(latest_report.audit_id, audit_id)
            self.assertEqual(latest_report.job_id, job_id)
            self.assertEqual(latest_report.output_path, str(export_root))
            self.assertEqual(latest_report.routed_root_path, str(routed_root))
            self.assertEqual(latest_report.summary_json_path, str(summary_json_path))
            self.assertEqual(latest_report.summary_txt_path, str(summary_txt_path))
            self.assertEqual(latest_report.total_rows, 2)
            self.assertEqual(latest_report.copied_count, 2)
            self.assertEqual(latest_report.missing_source_count, 0)
            self.assertEqual(latest_report.failed_copy_count, 0)
            self.assertEqual(latest_report.include_class_labels, list(DEFAULT_EXPORT_POLICY.include_class_labels))
            self.assertFalse(latest_report.final_only)
            self.assertEqual(latest_report.skipped_count, 0)
            self.assertEqual(latest_report.skipped_by_class_label, {})
            self.assertTrue(Path(csv_path).exists())
            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(summary_json_path).exists())
            self.assertTrue(Path(summary_txt_path).exists())
            self.assertTrue(latest_report.exported_at)
            db.close()

    def test_filtered_export_audit_reflects_policy_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            roster_path = tmp / 'ready.csv'
            image_root = tmp / 'images'
            export_root = tmp / 'exports'
            image_root.mkdir(parents=True)
            folder = image_root / 'A123'
            folder.mkdir()
            (folder / 'IMG_0001_primary.JPG').write_bytes(b'primary')
            (folder / 'IMG_0002_alt.JPG').write_bytes(b'alt')
            (folder / 'IMG_0003_group.JPG').write_bytes(b'group')

            with roster_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    'Child ID',
                    'Student firstname',
                    'Student lastname',
                    'Group',
                    'Access Code (1)',
                    'Barcode (1)',
                ])
                writer.writerow(['1', 'Rickey', 'Green', 'Team A', 'A123', '000123'])

            roster = load_roster(roster_path)
            scans = scan_image_root(image_root, roster)
            db = Database(tmp / 'audit_policy.db')
            job_id = db.create_job(roster, image_root, scans)
            db.connection.execute(
                "UPDATE images SET class_label = 'review_required', selected_final = 0 WHERE filename = ?",
                ('IMG_0002_alt.JPG',),
            )
            db.connection.execute(
                "UPDATE images SET class_label = 'reject', selected_final = 0 WHERE filename = ?",
                ('IMG_0003_group.JPG',),
            )
            db.connection.commit()

            policy = ExportPolicy(final_only=True)
            _, _, routed_root, _, _, audit_id = export_job_package_with_policy_and_audit(
                db,
                job_id,
                export_root,
                policy,
            )
            latest_report = get_latest_export_audit_report(db, job_id)

            self.assertGreater(audit_id, 0)
            self.assertIsNotNone(latest_report)
            assert latest_report is not None
            self.assertEqual(latest_report.audit_id, audit_id)
            self.assertEqual(latest_report.total_rows, 1)
            self.assertEqual(latest_report.copied_count, 1)
            self.assertEqual(latest_report.skipped_count, 2)
            self.assertEqual(latest_report.skipped_by_class_label['review_required'], 1)
            self.assertEqual(latest_report.skipped_by_class_label['reject'], 1)
            self.assertTrue(latest_report.final_only)
            self.assertEqual(latest_report.include_class_labels, list(DEFAULT_EXPORT_POLICY.include_class_labels))
            self.assertTrue((routed_root / 'student_solo_primary_candidate' / 'A123' / 'IMG_0001_primary.JPG').exists())
            self.assertFalse((routed_root / 'review_required' / 'A123' / 'IMG_0002_alt.JPG').exists())
            self.assertFalse((routed_root / 'reject' / 'A123' / 'IMG_0003_group.JPG').exists())
            db.close()

    def test_get_latest_export_audit_report_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db = Database(Path(tmp_dir) / 'empty.db')
            self.assertIsNone(get_latest_export_audit_report(db, 999))
            db.close()


if __name__ == '__main__':
    unittest.main()
