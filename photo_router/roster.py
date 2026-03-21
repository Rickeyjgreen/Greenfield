from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import REQUIRED_ROSTER_COLUMNS


class RosterValidationError(ValueError):
    pass


@dataclass(slots=True)
class RosterRow:
    child_id: str
    first_name: str
    last_name: str
    group_name: str
    access_code: str
    barcode_raw: str
    raw: dict[str, str]

    @property
    def display_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()


@dataclass(slots=True)
class LoadedRoster:
    path: Path
    rows: list[RosterRow]
    columns: list[str]


def _normalize_value(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def validate_columns(fieldnames: Iterable[str] | None) -> list[str]:
    columns = [col.strip() for col in (fieldnames or []) if col]
    missing = [col for col in REQUIRED_ROSTER_COLUMNS if col not in columns]
    if missing:
        raise RosterValidationError(
            'Ready_ CSV is missing required columns: ' + ', '.join(missing)
        )
    return columns


def _normalize_row(raw_row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_row.items():
        if not key:
            continue
        normalized[key.strip()] = _normalize_value(value)
    return normalized


def load_roster(csv_path: str | Path) -> LoadedRoster:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f'Roster file not found: {path}')

    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = validate_columns(reader.fieldnames)
        rows: list[RosterRow] = []
        for raw_row in reader:
            normalized = _normalize_row(raw_row)
            missing = [col for col in REQUIRED_ROSTER_COLUMNS if col not in normalized]
            if missing:
                raise RosterValidationError(
                    'Ready_ CSV row is missing required values for columns: ' + ', '.join(missing)
                )
            rows.append(
                RosterRow(
                    child_id=normalized['Child ID'],
                    first_name=normalized['Student firstname'],
                    last_name=normalized['Student lastname'],
                    group_name=normalized['Group'],
                    access_code=normalized['Access Code (1)'],
                    barcode_raw=normalized['Barcode (1)'],
                    raw=normalized,
                )
            )

    if not rows:
        raise RosterValidationError('Ready_ CSV contains no roster rows.')

    return LoadedRoster(path=path, rows=rows, columns=columns)
