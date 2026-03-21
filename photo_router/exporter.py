from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Iterable

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

ROUTED_EXPORT_DIRNAME = 'routed_by_class'


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

        class_dir = routed_root / _safe_path_component(row.get('class_label'), 'unclassified')
        folder_dir = class_dir / _safe_path_component(row.get('source_folder'), 'unknown_folder')
        _copy_to_routed_path(source_path, folder_dir)

    return routed_root


def export_package(rows: Iterable[dict], output_dir: str | Path) -> tuple[Path, Path, Path]:
    row_list = list(rows)
    csv_path, json_path = export_manifest(row_list, output_dir)
    routed_root = export_routed_files(row_list, output_dir)
    return csv_path, json_path, routed_root
