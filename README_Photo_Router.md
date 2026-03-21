# Photo Router

Windows-first local desktop scaffold for the Photo Router v1 Milestone 0 slice.

## Locked scope in this commit

- Ready_ CSV ingest with required-column validation
- Image-root folder scan with Access Code (1) default folder matching
- Capture-order image listing
- Local SQLite persistence
- Manual review table with class override and final-selected toggle
- CSV and JSON manifest export stub

## Out of scope in this commit

- ML identity grouping
- automatic quality ranking
- buddy/adult auto-classification
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

## Notes

- Source files are not mutated.
- Barcode values are preserved as text.
- All images start in `review_required` until manual review or later classifier work.
