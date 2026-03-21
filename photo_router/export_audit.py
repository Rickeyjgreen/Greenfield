from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .db import Database
from .exporter import ExportSummary, export_package_with_summary


@dataclass(slots=True)
class LatestExportAuditReport:
    audit_id: int
    job_id: int
    output_path: str
    routed_root_path: str
    summary_json_path: str
    summary_txt_path: str
    total_rows: int
    copied_count: int
    missing_source_count: int
    failed_copy_count: int
    exported_at: str

    def to_dict(self) -> dict:
        return asdict(self)


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


def get_latest_export_audit_report(
    database: Database,
    job_id: int,
) -> LatestExportAuditReport | None:
    latest = database.fetch_latest_export_audit(job_id)
    if latest is None:
        return None

    return LatestExportAuditReport(
        audit_id=int(latest['id']),
        job_id=int(latest['job_id']),
        output_path=str(latest['output_path']),
        routed_root_path=str(latest['routed_root_path']),
        summary_json_path=str(latest['summary_json_path']),
        summary_txt_path=str(latest['summary_txt_path']),
        total_rows=int(latest['total_rows']),
        copied_count=int(latest['copied_count']),
        missing_source_count=int(latest['missing_source_count']),
        failed_copy_count=int(latest['failed_copy_count']),
        exported_at=str(latest['exported_at']),
    )
