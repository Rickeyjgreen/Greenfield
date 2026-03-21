from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .classifier import classify_folder
from .constants import ROUTING_CLASSES
from .roster import LoadedRoster
from .scanner import FolderScan


SCHEMA = '''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roster_path TEXT NOT NULL,
    image_root TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roster_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    child_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    access_code TEXT NOT NULL,
    barcode_raw TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    folder_name TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    folder_key TEXT NOT NULL,
    roster_row_id INTEGER,
    matched INTEGER NOT NULL DEFAULT 0,
    image_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (roster_row_id) REFERENCES roster_rows(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    modified_time REAL NOT NULL,
    class_label TEXT NOT NULL DEFAULT 'review_required',
    selected_final INTEGER NOT NULL DEFAULT 0,
    manual_override INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    review_reason TEXT NOT NULL DEFAULT 'manual_review_pending',
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
);
'''


class Database:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def create_job(self, roster: LoadedRoster, image_root: str | Path, scans: list[FolderScan]) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            'INSERT INTO jobs (roster_path, image_root) VALUES (?, ?)',
            (str(roster.path), str(image_root)),
        )
        job_id = int(cursor.lastrowid)

        roster_map: dict[str, int] = {}
        for row in roster.rows:
            cursor.execute(
                '''
                INSERT INTO roster_rows (
                    job_id, child_id, first_name, last_name, group_name, access_code, barcode_raw, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    job_id,
                    row.child_id,
                    row.first_name,
                    row.last_name,
                    row.group_name,
                    row.access_code,
                    row.barcode_raw,
                    json.dumps(row.raw, ensure_ascii=False),
                ),
            )
            roster_map[row.access_code] = int(cursor.lastrowid)

        for scan in scans:
            roster_row_id = roster_map.get(scan.folder_key) if scan.roster_row else None
            cursor.execute(
                '''
                INSERT INTO folders (
                    job_id, folder_name, folder_path, folder_key, roster_row_id, matched, image_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    job_id,
                    scan.folder_name,
                    str(scan.folder_path),
                    scan.folder_key,
                    roster_row_id,
                    1 if scan.matched else 0,
                    len(scan.images),
                ),
            )
            folder_id = int(cursor.lastrowid)
            classifications = classify_folder(scan)
            for image, classification in zip(scan.images, classifications):
                cursor.execute(
                    '''
                    INSERT INTO images (
                        folder_id, order_index, filename, file_path, modified_time,
                        class_label, selected_final, confidence, review_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        folder_id,
                        image.order_index,
                        image.filename,
                        str(image.path),
                        image.modified_time,
                        classification.class_label,
                        1 if classification.selected_final else 0,
                        classification.confidence,
                        classification.review_reason,
                    ),
                )

        self.connection.commit()
        return job_id

    def fetch_folders(self, job_id: int) -> list[sqlite3.Row]:
        query = '''
        SELECT
            f.id,
            f.folder_name,
            f.folder_path,
            f.folder_key,
            f.matched,
            f.image_count,
            r.child_id,
            r.first_name,
            r.last_name,
            r.group_name,
            r.access_code,
            r.barcode_raw
        FROM folders f
        LEFT JOIN roster_rows r ON r.id = f.roster_row_id
        WHERE f.job_id = ?
        ORDER BY f.folder_name COLLATE NOCASE
        '''
        return list(self.connection.execute(query, (job_id,)))

    def fetch_images_for_folder(self, folder_id: int) -> list[sqlite3.Row]:
        query = '''
        SELECT id, order_index, filename, file_path, class_label, selected_final, manual_override, confidence, review_reason
        FROM images
        WHERE folder_id = ?
        ORDER BY order_index ASC, filename COLLATE NOCASE ASC
        '''
        return list(self.connection.execute(query, (folder_id,)))

    def update_image_review(self, image_id: int, class_label: str, selected_final: bool) -> None:
        if class_label not in ROUTING_CLASSES:
            raise ValueError(f'Invalid class label: {class_label}')
        self.connection.execute(
            '''
            UPDATE images
            SET class_label = ?, selected_final = ?, manual_override = 1,
                review_reason = CASE WHEN ? = 1 THEN 'manually_marked_final' ELSE 'manual_review_pending' END
            WHERE id = ?
            ''',
            (class_label, 1 if selected_final else 0, 1 if selected_final else 0, image_id),
        )
        self.connection.commit()

    def clear_folder_final_selection(self, folder_id: int, except_image_id: int) -> None:
        self.connection.execute(
            'UPDATE images SET selected_final = 0 WHERE folder_id = ? AND id != ?',
            (folder_id, except_image_id),
        )
        self.connection.commit()

    def fetch_export_rows(self, job_id: int) -> list[dict[str, Any]]:
        query = '''
        SELECT
            j.id AS job_id,
            f.folder_name AS source_folder,
            i.filename AS source_filename,
            i.file_path,
            i.class_label,
            i.selected_final,
            i.confidence,
            i.review_reason,
            r.group_name,
            r.child_id,
            r.access_code,
            r.barcode_raw
        FROM jobs j
        INNER JOIN folders f ON f.job_id = j.id
        INNER JOIN images i ON i.folder_id = f.id
        LEFT JOIN roster_rows r ON r.id = f.roster_row_id
        WHERE j.id = ?
        ORDER BY f.folder_name COLLATE NOCASE, i.order_index ASC
        '''
        rows = []
        for row in self.connection.execute(query, (job_id,)):
            rows.append(dict(row))
        return rows
