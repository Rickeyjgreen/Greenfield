from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from photo_router.roster import RosterValidationError, load_roster
from photo_router.scanner import scan_image_root


class PhotoRouterTests(unittest.TestCase):
    def test_load_roster_requires_locked_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / 'broken.csv'
            with csv_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['Child ID', 'Student firstname'])
                writer.writerow(['1', 'Rickey'])
            with self.assertRaises(RosterValidationError):
                load_roster(csv_path)

    def test_load_roster_normalizes_header_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / 'ready_whitespace.csv'
            with csv_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    'Child ID ',
                    'Student firstname ',
                    'Student lastname ',
                    'Group ',
                    'Access Code (1) ',
                    'Barcode (1) ',
                ])
                writer.writerow(['1', 'Rickey', 'Green', 'Team A', 'A123', '000123'])

            roster = load_roster(csv_path)
            self.assertEqual(len(roster.rows), 1)
            self.assertEqual(roster.rows[0].access_code, 'A123')
            self.assertEqual(roster.rows[0].barcode_raw, '000123')

    def test_scan_matches_access_code_and_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            roster_path = tmp / 'ready.csv'
            image_root = tmp / 'images'
            image_root.mkdir(parents=True)
            folder = image_root / 'A123'
            folder.mkdir()
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
            (folder / 'IMG_0002.JPG').write_bytes(b'b')
            (folder / 'IMG_0001.JPG').write_bytes(b'a')

            roster = load_roster(roster_path)
            scans = scan_image_root(image_root, roster)

            self.assertEqual(len(scans), 1)
            self.assertTrue(scans[0].matched)
            self.assertEqual([img.filename for img in scans[0].images], ['IMG_0001.JPG', 'IMG_0002.JPG'])


if __name__ == '__main__':
    unittest.main()
