from __future__ import annotations

import json
from pathlib import Path

from .db import Database
from .exporter import ExportSummary, export_package_with_summary


def export_job_package_with_audit(
    database: Database,
    job_id: int,
    output_dir: str | Path,
) -> tuple[Path, Path, Path, Path, Path, int]:
    rows = database.fetch_export_rows(job_id)
    csv_path, manifest_json_path, routed_root, summary_json_path, summary_txt_path = export_package_with_summary(
        rows,
        output_dir,
    )

    summary_data = json.loads(Path(summary_json_path).read_text(encoding='utf-8'))
    summary = ExportSummary(
        total_rows=summary_data['total_rows'],
        copied_count=summary_data['copied_count'],
        missing_source_count=summary_data['missing_source_count'],
        failed_copy_count=summary_data['failed_copy_count'],
        rows_by_class_label=summary_data['rows_by_class_label'],
        copied_by_class_label=summary_data['copied_by_class_label'],
        missing_by_class_label=summary_data['missing_by_class_label'],
        failed_by_class_label=summary_data['failed_by_class_label'],
        failures=[],
    )
    audit_id = database.record_export_audit(
        job_id=job_id,
        output_path=output_dir,
        routed_root_path=routed_root,
        summary_json_path=summary_json_path,
        summary_txt_path=summary_txt_path,
        summary=summary,
    )
    return csv_path, manifest_json_path, routed_root, summary_json_path, summary_txt_path, audit_id
