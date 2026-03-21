from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

EXPORT_COLUMNS = [
    'job_id',
    'source_folder',
    'source_filename',
    'file_path',
    'class_label',
    'selected_final',
    'confidence',
    'review_reason',
    'group_name',
    'child_id',
    'access_code',
    'barcode_raw',
]

DEFAULT_INCLUDED_CLASS_LABELS = (
    'student_solo_primary_candidate',
    'student_solo_alt_candidate',
    'adult_solo_candidate',
    'buddy_multi_person',
)

ROUTED_EXPORT_DIRNAME = 'routed_by_class'
SUMMARY_JSON_FILENAME = 'photo_router_export_summary.json'
SUMMARY_TXT_FILENAME = 'photo_router_export_summary.txt'


@dataclass(frozen=True, slots=True)
class ExportPolicy:
    include_class_labels: tuple[str, ...] = DEFAULT_INCLUDED_CLASS_LABELS
    final_only: bool = False

    def normalized_labels(self) -> tuple[str, ...]:
        unique: list[str] = []
        for label in self.include_class_labels:
            cleaned = str(label).strip()
            if cleaned and cleaned not in unique:
                unique.append(cleaned)
        return tuple(unique)

    def to_dict(self) -> dict[str, Any]:
        return {
            'include_class_labels': list(self.normalized_labels()),
            'final_only': self.final_only,
        }


DEFAULT_EXPORT_POLICY = ExportPolicy()


@dataclass(slots=True)
class ExportFailure:
    class_label: str
    source_folder: str
    source_filename: str
    file_path: str
    failure_type: str
    error: str


@dataclass(slots=True)
class ExportSummary:
    total_rows: int = 0
    copied_count: int = 0
    missing_source_count: int = 0
    failed_copy_count: int = 0
    skipped_count: int = 0
    rows_by_class_label: dict[str, int] = field(default_factory=dict)
    copied_by_class_label: dict[str, int] = field(default_factory=dict)
    missing_by_class_label: dict[str, int] = field(default_factory=dict)
    failed_by_class_label: dict[str, int] = field(default_factory=dict)
    skipped_by_class_label: dict[str, int] = field(default_factory=dict)
    export_policy: dict[str, Any] = field(default_factory=dict)
    failures: list[ExportFailure] = field(default_factory=list)

    def _increment(self, bucket: dict[str, int], class_label: str) -> None:
        bucket[class_label] = bucket.get(class_label, 0) + 1

    def note_row(self, class_label: str) -> None:
        self.total_rows += 1
        self._increment(self.rows_by_class_label, class_label)

    def note_copied(self, class_label: str) -> None:
        self.copied_count += 1
        self._increment(self.copied_by_class_label, class_label)

    def note_missing(self, failure: ExportFailure) -> None:
        self.missing_source_count += 1
        self._increment(self.missing_by_class_label, failure.class_label)
        self.failures.append(failure)

    def note_failed_copy(self, failure: ExportFailure) -> None:
        self.failed_copy_count += 1
        self._increment(self.failed_by_class_label, failure.class_label)
        self.failures.append(failure)

    def note_skipped(self, class_label: str) -> None:
        self.skipped_count += 1
        self._increment(self.skipped_by_class_label, class_label)

    def to_dict(self) -> dict:
        return {
            'total_rows': self.total_rows,
            'copied_count': self.copied_count,
            'missing_source_count': self.missing_source_count,
            'failed_copy_count': self.failed_copy_count,
            'skipped_count': self.skipped_count,
            'rows_by_class_label': self.rows_by_class_label,
            'copied_by_class_label': self.copied_by_class_label,
            'missing_by_class_label': self.missing_by_class_label,
            'failed_by_class_label': self.failed_by_class_label,
            'skipped_by_class_label': self.skipped_by_class_label,
            'export_policy': self.export_policy,
            'failures': [asdict(failure) for failure in self.failures],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ExportSummary':
        summary = cls(
            total_rows=int(data.get('total_rows', 0)),
            copied_count=int(data.get('copied_count', 0)),
            missing_source_count=int(data.get('missing_source_count', 0)),
            failed_copy_count=int(data.get('failed_copy_count', 0)),
            skipped_count=int(data.get('skipped_count', 0)),
            rows_by_class_label=dict(data.get('rows_by_class_label', {})),
            copied_by_class_label=dict(data.get('copied_by_class_label', {})),
            missing_by_class_label=dict(data.get('missing_by_class_label', {})),
            failed_by_class_label=dict(data.get('failed_by_class_label', {})),
            skipped_by_class_label=dict(data.get('skipped_by_class_label', {})),
            export_policy=dict(data.get('export_policy', {})),
        )
        for item in data.get('failures', []):
            summary.failures.append(ExportFailure(**item))
        return summary


def _resolve_policy(policy: ExportPolicy | None) -> ExportPolicy:
    return policy if policy is not None else DEFAULT_EXPORT_POLICY


def _safe_path_component(value: object, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        return fallback
    cleaned = []
    for char in text:
        if char.isalnum() or char in {'-', '_', '.'}:
            cleaned.append(char)
        elif char.isspace():
            cleaned.append('_')
        else:
            cleaned.append('_')
    normalized = ''.join(cleaned).strip('._')
    return normalized or fallback


def _row_class_label_value(row: dict) -> str:
    text = str(row.get('class_label') or '').strip()
    return text or 'unclassified'


def _row_class_label_path(row: dict) -> str:
    return _safe_path_component(_row_class_label_value(row), 'unclassified')


def _row_selected_final(row: dict) -> bool:
    value = row.get('selected_final')
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes'}
    return bool(value)


def filter_rows_for_export(
    rows: Iterable[dict],
    policy: ExportPolicy | None = None,
) -> tuple[list[dict], ExportSummary]:
    resolved_policy = _resolve_policy(policy)
    include_set = set(resolved_policy.normalized_labels())
    summary = ExportSummary(export_policy=resolved_policy.to_dict())
    included_rows: list[dict] = []

    for row in rows:
        class_label = _row_class_label_value(row)
        if class_label not in include_set:
            summary.note_skipped(class_label)
            continue
        if resolved_policy.final_only and not _row_selected_final(row):
            summary.note_skipped(class_label)
            continue
        included_rows.append(row)
        summary.note_row(class_label)

    return included_rows, summary


def export_manifest(rows: Iterable[dict], output_dir: str | Path) -> tuple[Path, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_path = output_path / 'photo_router_manifest.csv'
    json_path = output_path / 'photo_router_manifest.json'

    row_list = list(rows)
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for row in row_list:
            writer.writerow({column: row.get(column) for column in EXPORT_COLUMNS})

    with json_path.open('w', encoding='utf-8') as handle:
        json.dump(row_list, handle, indent=2)

    return csv_path, json_path


def _copy_to_routed_path(source_path: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    candidate = destination_dir / source_path.name
    if not candidate.exists():
        shutil.copy2(source_path, candidate)
        return candidate

    stem = source_path.stem
    suffix = source_path.suffix
    counter = 2
    while True:
        candidate = destination_dir / f'{stem}_{counter}{suffix}'
        if not candidate.exists():
            shutil.copy2(source_path, candidate)
            return candidate
        counter += 1


def export_routed_files(rows: Iterable[dict], output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    routed_root = output_path / ROUTED_EXPORT_DIRNAME
    routed_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        source_path = Path(str(row.get('file_path') or ''))
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f'Source image not found for export: {source_path}')

        class_dir = routed_root / _row_class_label_path(row)
        folder_dir = class_dir / _safe_path_component(row.get('source_folder'), 'unknown_folder')
        _copy_to_routed_path(source_path, folder_dir)

    return routed_root


def export_routed_files_with_summary(
    rows: Iterable[dict],
    output_dir: str | Path,
    policy: ExportPolicy | None = None,
) -> tuple[Path, ExportSummary]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    routed_root = output_path / ROUTED_EXPORT_DIRNAME
    routed_root.mkdir(parents=True, exist_ok=True)

    included_rows, summary = filter_rows_for_export(rows, policy)
    for row in included_rows:
        class_label = _row_class_label_value(row)
        source_folder = _safe_path_component(row.get('source_folder'), 'unknown_folder')
        source_filename = str(row.get('source_filename') or Path(str(row.get('file_path') or '')).name)
        source_path = Path(str(row.get('file_path') or ''))

        if not source_path.exists() or not source_path.is_file():
            summary.note_missing(
                ExportFailure(
                    class_label=class_label,
                    source_folder=source_folder,
                    source_filename=source_filename,
                    file_path=str(source_path),
                    failure_type='missing_source',
                    error='Source image not found',
                )
            )
            continue

        class_dir = routed_root / _safe_path_component(class_label, 'unclassified')
        folder_dir = class_dir / source_folder
        try:
            _copy_to_routed_path(source_path, folder_dir)
            summary.note_copied(class_label)
        except OSError as exc:
            summary.note_failed_copy(
                ExportFailure(
                    class_label=class_label,
                    source_folder=source_folder,
                    source_filename=source_filename,
                    file_path=str(source_path),
                    failure_type='copy_error',
                    error=str(exc),
                )
            )

    return routed_root, summary


def write_export_summary(summary: ExportSummary, output_dir: str | Path) -> tuple[Path, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / SUMMARY_JSON_FILENAME
    txt_path = output_path / SUMMARY_TXT_FILENAME

    with json_path.open('w', encoding='utf-8') as handle:
        json.dump(summary.to_dict(), handle, indent=2)

    policy = summary.export_policy or DEFAULT_EXPORT_POLICY.to_dict()
    lines = [
        'Photo Router Export Summary',
        f"Include class labels: {', '.join(policy.get('include_class_labels', [])) or 'none'}",
        f"Final only: {bool(policy.get('final_only', False))}",
        f'Total exported rows: {summary.total_rows}',
        f'Copied: {summary.copied_count}',
        f'Missing source: {summary.missing_source_count}',
        f'Failed copy: {summary.failed_copy_count}',
        f'Skipped by policy: {summary.skipped_count}',
        '',
        'Exported rows by class label:',
    ]
    for class_label in sorted(summary.rows_by_class_label):
        lines.append(f'- {class_label}: {summary.rows_by_class_label[class_label]}')
    if not summary.rows_by_class_label:
        lines.append('- none')

    lines.extend(['', 'Copied by class label:'])
    if summary.copied_by_class_label:
        for class_label in sorted(summary.copied_by_class_label):
            lines.append(f'- {class_label}: {summary.copied_by_class_label[class_label]}')
    else:
        lines.append('- none')

    lines.extend(['', 'Skipped by class label:'])
    if summary.skipped_by_class_label:
        for class_label in sorted(summary.skipped_by_class_label):
            lines.append(f'- {class_label}: {summary.skipped_by_class_label[class_label]}')
    else:
        lines.append('- none')

    lines.extend(['', 'Missing by class label:'])
    if summary.missing_by_class_label:
        for class_label in sorted(summary.missing_by_class_label):
            lines.append(f'- {class_label}: {summary.missing_by_class_label[class_label]}')
    else:
        lines.append('- none')

    lines.extend(['', 'Failed copy by class label:'])
    if summary.failed_by_class_label:
        for class_label in sorted(summary.failed_by_class_label):
            lines.append(f'- {class_label}: {summary.failed_by_class_label[class_label]}')
    else:
        lines.append('- none')

    if summary.failures:
        lines.extend(['', 'Failures:'])
        for failure in summary.failures:
            lines.append(
                f'- {failure.failure_type}: {failure.class_label} / {failure.source_folder} / {failure.source_filename} / {failure.file_path} / {failure.error}'
            )

    with txt_path.open('w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')

    return json_path, txt_path


def export_package_with_summary(
    rows: Iterable[dict],
    output_dir: str | Path,
    policy: ExportPolicy | None = None,
) -> tuple[Path, Path, Path, Path, Path]:
    row_list = list(rows)
    included_rows, _ = filter_rows_for_export(row_list, policy)
    csv_path, manifest_json_path = export_manifest(included_rows, output_dir)
    routed_root, summary = export_routed_files_with_summary(row_list, output_dir, policy=policy)
    summary_json_path, summary_txt_path = write_export_summary(summary, output_dir)
    return csv_path, manifest_json_path, routed_root, summary_json_path, summary_txt_path


def export_package_with_policy(
    rows: Iterable[dict],
    output_dir: str | Path,
    policy: ExportPolicy,
) -> tuple[Path, Path, Path, Path, Path]:
    return export_package_with_summary(rows, output_dir, policy=policy)


def export_package(
    rows: Iterable[dict],
    output_dir: str | Path,
    policy: ExportPolicy | None = None,
) -> tuple[Path, Path, Path]:
    csv_path, manifest_json_path, routed_root, _, _ = export_package_with_summary(rows, output_dir, policy=policy)
    return csv_path, manifest_json_path, routed_root
