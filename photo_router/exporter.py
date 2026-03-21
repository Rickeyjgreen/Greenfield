from __future__ import annotations

import csv
import json
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
