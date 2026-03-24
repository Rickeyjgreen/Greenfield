from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from photo_router.preview import load_preview_image


class PreviewTests(unittest.TestCase):
    def test_load_preview_image_supports_jpg_and_tif(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jpg_path = tmp / 'sample.jpg'
            tif_path = tmp / 'sample.tif'
            Image.new('RGB', (100, 60), color='red').save(jpg_path)
            Image.new('RGB', (120, 80), color='blue').save(tif_path)

            jpg_preview, jpg_error = load_preview_image(jpg_path)
            tif_preview, tif_error = load_preview_image(tif_path)

            self.assertIsNotNone(jpg_preview)
            self.assertIsNone(jpg_error)
            self.assertIsNotNone(tif_preview)
            self.assertIsNone(tif_error)
            assert jpg_preview is not None
            assert tif_preview is not None
            self.assertGreater(jpg_preview.width(), 0)
            self.assertGreater(jpg_preview.height(), 0)
            self.assertGreater(tif_preview.width(), 0)
            self.assertGreater(tif_preview.height(), 0)

    def test_load_preview_image_handles_missing_file(self) -> None:
        preview, error = load_preview_image(Path('does-not-exist.tif'))
        self.assertIsNone(preview)
        self.assertIsNotNone(error)


if __name__ == '__main__':
    unittest.main()
