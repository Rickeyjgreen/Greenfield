from __future__ import annotations

import unittest
from pathlib import Path

from photo_router.classifier import classify_folder
from photo_router.roster import RosterRow
from photo_router.scanner import FolderScan, ScannedImage


class ClassifierTests(unittest.TestCase):
    def _matched_scan(self, filenames: list[str]) -> FolderScan:
        roster_row = RosterRow(
            child_id='1',
            first_name='Rickey',
            last_name='Green',
            group_name='Team A',
            access_code='A123',
            barcode_raw='000123',
            raw={},
        )
        images = [
            ScannedImage(
                order_index=index,
                filename=filename,
                path=Path(f'/tmp/{filename}'),
                modified_time=float(index),
            )
            for index, filename in enumerate(filenames, start=1)
        ]
        return FolderScan(
            folder_name='A123',
            folder_path=Path('/tmp/A123'),
            folder_key='A123',
            roster_row=roster_row,
            images=images,
        )

    def test_filename_hints_seed_primary_alt_and_buddy(self) -> None:
        scan = self._matched_scan([
            'IMG_0001_primary.JPG',
            'IMG_0002_alt.JPG',
            'IMG_0003_group.JPG',
        ])

        results = classify_folder(scan)

        self.assertEqual(results[0].class_label, 'student_solo_primary_candidate')
        self.assertTrue(results[0].selected_final)
        self.assertEqual(results[0].review_reason, 'filename_primary_hint')
        self.assertEqual(results[1].class_label, 'student_solo_alt_candidate')
        self.assertFalse(results[1].selected_final)
        self.assertEqual(results[2].class_label, 'buddy_multi_person')

    def test_unmatched_folder_stays_in_review_queue(self) -> None:
        scan = FolderScan(
            folder_name='NO_MATCH',
            folder_path=Path('/tmp/NO_MATCH'),
            folder_key='NO_MATCH',
            roster_row=None,
            images=[
                ScannedImage(
                    order_index=1,
                    filename='IMG_0001.JPG',
                    path=Path('/tmp/NO_MATCH/IMG_0001.JPG'),
                    modified_time=1.0,
                )
            ],
        )

        results = classify_folder(scan)

        self.assertEqual(results[0].class_label, 'review_required')
        self.assertFalse(results[0].selected_final)
        self.assertEqual(results[0].review_reason, 'unmatched_folder_requires_review')

    def test_only_one_final_selection_survives(self) -> None:
        scan = self._matched_scan([
            'IMG_0001_primary.JPG',
            'IMG_0002_primary.JPG',
            'IMG_0003_alt.JPG',
        ])

        results = classify_folder(scan)
        final_count = sum(1 for result in results if result.selected_final)

        self.assertEqual(final_count, 1)
        self.assertEqual(results[0].class_label, 'student_solo_primary_candidate')
        self.assertTrue(results[0].selected_final)
        self.assertEqual(results[1].class_label, 'student_solo_alt_candidate')
        self.assertFalse(results[1].selected_final)
        self.assertEqual(results[1].review_reason, 'demoted_after_multiple_final_candidates')


if __name__ == '__main__':
    unittest.main()
