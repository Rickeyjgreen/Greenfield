from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image, TiffImagePlugin

from photo_router.roster import RosterValidationError, load_roster
from photo_router.scanner import UNMATCHED_ROOT_GROUP, scan_image_root


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

    def test_scan_flat_root_matches_tiff_copyright_to_barcode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            roster_path = tmp / 'ready.csv'
            image_root = tmp / 'flat_images'
            image_root.mkdir(parents=True)
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
                writer.writerow(['1', 'Rickey', 'Green', 'Team A', 'A123', '31756845281541'])

            matched_path = image_root / 'IMG_0001.tif'
            unmatched_path = image_root / 'IMG_0002.tif'
            image = Image.new('RGB', (8, 8), color='white')
            tiffinfo = TiffImagePlugin.ImageFileDirectory_v2()
            tiffinfo[33432] = '31756845281541'
            image.save(matched_path, tiffinfo=tiffinfo)
            image.save(unmatched_path)

            roster = load_roster(roster_path)
            scans = scan_image_root(image_root, roster)

            self.assertEqual(len(scans), 2)
            matched_scan = next(scan for scan in scans if scan.folder_key == '31756845281541')
            unmatched_scan = next(scan for scan in scans if scan.folder_key == UNMATCHED_ROOT_GROUP)
            self.assertTrue(matched_scan.matched)
            self.assertEqual(matched_scan.roster_row.barcode_raw, '31756845281541')
            self.assertEqual([img.filename for img in matched_scan.images], ['IMG_0001.tif'])
            self.assertFalse(unmatched_scan.matched)
            self.assertEqual([img.filename for img in unmatched_scan.images], ['IMG_0002.tif'])


if __name__ == '__main__':
    unittest.main()
