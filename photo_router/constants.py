from pathlib import Path

APP_NAME = 'Photo Router'
APP_DIR_NAME = '.photo_router'
DB_FILENAME = 'photo_router.db'

REQUIRED_ROSTER_COLUMNS = [
    'Child ID',
    'Student firstname',
    'Student lastname',
    'Group',
    'Access Code (1)',
    'Barcode (1)',
]

ROUTING_CLASSES = [
    'student_solo_primary_candidate',
    'student_solo_alt_candidate',
    'adult_solo_candidate',
    'buddy_multi_person',
    'review_required',
    'reject',
]

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp'}


def get_app_data_dir() -> Path:
    path = Path.home() / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_db_path() -> Path:
    return get_app_data_dir() / DB_FILENAME
