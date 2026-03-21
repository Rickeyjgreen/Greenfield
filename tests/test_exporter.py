from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from photo_router.exporter import export_package, export_routed_files


class ExporterTests(unittest.TestCase):
    def test_export_package_writes_manifest_and_routed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            source_dir = tmp / 'source'
            source_dir.mkdir()
            first = source_dir / 'IMG_0001_primary.JPG'
            second = source_dir / 'IMG_0002_alt.JPG'
            first.write_bytes(b'primary')
            second.write_bytes(b'alt')

            rows = [
                {
                    'job_id': 1,
                    'source_folder': 'A123',
                    'source_filename': first.name,
                    'file_path': str(first),
                    'class_label': 'student_solo_primary_candidate',
                    'selected_final': 1,
                    'confidence': 0.9,
                    'review_reason': 'filename_primary_hint',
                    'group_name': 'Team A',
                    'child_id': '1001',
                    'access_code': 'A123',
                    'barcode_raw': '000123',
                },
                {
                    'job_id': 1,
                    'source_folder': 'A123',
                    'source_filename': second.name,
                    'file_path': str(second),
                    'class_label': 'student_solo_alt_candidate',
                    'selected_final': 0,
                    'confidence': 0.7,
                    'review_reason': 'filename_alt_hint',
                    'group_name': 'Team A',
                    'child_id': '1001',
                    'access_code': 'A123',
                    'barcode_raw': '000123',
                },
            ]

            csv_path, json_path, routed_root = export_package(rows, tmp / 'exports')

            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue((routed_root / 'student_solo_primary_candidate' / 'A123' / first.name).exists())
            self.assertTrue((routed_root / 'student_solo_alt_candidate' / 'A123' / second.name).exists())
            self.assertEqual(first.read_bytes(), (routed_root / 'student_solo_primary_candidate' / 'A123' / first.name).read_bytes())

    def test_export_routed_files_raises_for_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            rows = [
                {
                    'file_path': str(Path(tmp_dir) / 'missing.JPG'),
                    'class_label': 'review_required',
                    'source_folder': 'A123',
                }
            ]
            with self.assertRaises(FileNotFoundError):
                export_routed_files(rows, Path(tmp_dir) / 'exports')

    def test_export_routed_files_deduplicates_name_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            one_dir = tmp / 'source_one'
            two_dir = tmp / 'source_two'
            one_dir.mkdir()
            two_dir.mkdir()
            first = one_dir / 'IMG_0001.JPG'
            second = two_dir / 'IMG_0001.JPG'
            first.write_bytes(b'first')
            second.write_bytes(b'second')

            rows = [
                {
                    'file_path': str(first),
                    'class_label': 'review_required',
                    'source_folder': 'A123',
                },
                {
                    'file_path': str(second),
                    'class_label': 'review_required',
                    'source_folder': 'A123',
                },
            ]

            routed_root = export_routed_files(rows, tmp / 'exports')
            target_dir = routed_root / 'review_required' / 'A123'
            self.assertTrue((target_dir / 'IMG_0001.JPG').exists())
            self.assertTrue((target_dir / 'IMG_0001_2.JPG').exists())


if __name__ == '__main__':
    unittest.main()
