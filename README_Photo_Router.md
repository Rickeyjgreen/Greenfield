# Photo Router

Windows-first local desktop scaffold for the Photo Router v1 Milestone 0 slice.

## Locked scope in this commit

- Ready_ CSV ingest with required-column validation
- Image-root folder scan with Access Code (1) default folder matching
- Capture-order image listing
- Local SQLite persistence
- Deterministic ingest-time seed classification
- Manual review table with class override and final-selected toggle
- CSV and JSON manifest export
- Routed export folders by class label without mutating source files
- Export summary reporting with class-label counts and missing/failed copy details
- DB-backed export audit metadata for latest export path and counts
- Export filtering policy support for class inclusion and final-only export

## Out of scope in this commit

- ML identity grouping
- automatic quality ranking from image content
- Pixnub integration
- Actual_ to Ready_ conversion

## Required roster columns

- Child ID
- Student firstname
- Student lastname
- Group
- Access Code (1)
- Barcode (1)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m photo_router.app
```

## Smoke check

```bash
set PYTHONPATH=.
python scripts/smoke_run.py
python -m unittest discover -s tests
```

## Export behavior

- Manifest files are written to the export root.
- Routed image copies are written to `routed_by_class/<class_label>/<source_folder>/`.
- Export summary files are written to:
  - `photo_router_export_summary.json`
  - `photo_router_export_summary.txt`
- Export audits are persisted in SQLite with latest output path, summary paths, policy settings, and summary counts.
- Default export policy includes only:
  - `student_solo_primary_candidate`
  - `student_solo_alt_candidate`
  - `adult_solo_candidate`
  - `buddy_multi_person`
- Default export policy excludes:
  - `review_required`
  - `reject`
- Optional `final_only=True` export policy exports only rows with `selected_final` truthy.
- Source files are preserved and never mutated.
- Name collisions in routed output are deduplicated with numeric suffixes.
- Missing source images are reported in the export summary.

## Notes

- Barcode values are preserved as text.
- Manual review can still override all seeded classifications.
