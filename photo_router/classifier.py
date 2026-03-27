from __future__ import annotations

from dataclasses import dataclass

from .scanner import FolderScan, ScannedImage


@dataclass(slots=True)
class ClassificationResult:
    class_label: str
    selected_final: bool
    confidence: float | None
    review_reason: str


PRIMARY_HINTS = ('primary', 'hero', 'best', 'solo')
ALT_HINTS = ('alt', 'alternate', 'extra')
ADULT_HINTS = ('adult', 'coach', 'staff', 'parent')
BUDDY_HINTS = ('buddy', 'group', 'team', 'multi', 'pair')
REJECT_HINTS = ('reject', 'blur', 'closedeyes', 'duplicate', 'bad')


def _image_name_tokens(image: ScannedImage) -> str:
    return image.filename.lower()


def classify_image(scan: FolderScan, image: ScannedImage, image_count: int) -> ClassificationResult:
    filename = _image_name_tokens(image)

    for hint in REJECT_HINTS:
        if hint in filename:
            return ClassificationResult('reject', False, 0.1, 'filename_reject_hint')

    for hint in BUDDY_HINTS:
        if hint in filename:
            return ClassificationResult('buddy_multi_person', False, 0.35, 'filename_buddy_hint')

    for hint in ADULT_HINTS:
        if hint in filename:
            return ClassificationResult('adult_solo_candidate', False, 0.55, 'filename_adult_hint')

    if not scan.matched:
        return ClassificationResult('review_required', False, 0.2, 'unmatched_folder_requires_review')

    for hint in PRIMARY_HINTS:
        if hint in filename:
            return ClassificationResult('student_solo_primary_candidate', True, 0.9, 'filename_primary_hint')

    for hint in ALT_HINTS:
        if hint in filename:
            return ClassificationResult('student_solo_alt_candidate', False, 0.72, 'filename_alt_hint')

    if image_count == 1:
        return ClassificationResult('student_solo_primary_candidate', True, 0.8, 'single_image_in_matched_folder')

    if image.order_index == 1:
        return ClassificationResult('student_solo_primary_candidate', True, 0.68, 'first_image_in_matched_folder')

    if image.order_index <= 3:
        return ClassificationResult('student_solo_alt_candidate', False, 0.6, 'early_image_in_matched_folder')

    return ClassificationResult('review_required', False, 0.4, 'default_review_queue')


def classify_folder(scan: FolderScan) -> list[ClassificationResult]:
    results = [classify_image(scan, image, len(scan.images)) for image in scan.images]

    final_indexes = [index for index, result in enumerate(results) if result.selected_final]
    if len(final_indexes) > 1:
        keep_index = final_indexes[0]
        normalized: list[ClassificationResult] = []
        for index, result in enumerate(results):
            if index == keep_index:
                normalized.append(result)
            elif result.selected_final:
                normalized.append(
                    ClassificationResult(
                        class_label='student_solo_alt_candidate'
                        if result.class_label == 'student_solo_primary_candidate'
                        else result.class_label,
                        selected_final=False,
                        confidence=result.confidence,
                        review_reason='demoted_after_multiple_final_candidates',
                    )
                )
            else:
                normalized.append(result)
        return normalized

    return results
