import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from hak_ocr.grid_detection import _clusters, detect_grid, rotate_image


class GridUtilsTests(unittest.TestCase):
    def test_close_lines_merge(self):
        self.assertEqual(_clusters([20, 21, 22, 60, 61]), [21, 60])

    def test_empty(self):
        self.assertEqual(_clusters([]), [])

    def test_synthetic_grid_in_cropped_document(self):
        try:
            from PIL import Image, ImageDraw
            import cv2
        except ImportError:
            self.skipTest("Optional image dependencies unavailable")
        with TemporaryDirectory() as directory:
            image = Image.new("RGB", (840, 520), "white")
            draw = ImageDraw.Draw(image)
            # Actual table occupies a small fraction of the full document.
            for x in range(120, 721, 40):
                draw.line((x, 200, x, 400), fill="black", width=2)
            for y in range(200, 401, 25):
                draw.line((120, y, 720, y), fill="black", width=2)
            path = Path(directory) / "sample.png"
            image.save(path)
            result = detect_grid(path, expected_vertical_lines=16,
                                 expected_horizontal_lines=9)
            self.assertTrue(result["grid_found"])
            self.assertEqual(len(result["xs"]), 16)
            self.assertEqual(len(result["ys"]), 9)
            self.assertTrue(result["layout_complete"])
            self.assertFalse(result["verified"])

    def test_incomplete_grid_is_never_approved(self):
        try:
            from PIL import Image, ImageDraw
            import cv2
        except ImportError:
            self.skipTest("Optional image dependencies unavailable")
        with TemporaryDirectory() as directory:
            image = Image.new("RGB", (400, 260), "white")
            draw = ImageDraw.Draw(image)
            for x in (50, 100, 150, 200, 250, 300):
                draw.line((x, 70, x, 200), fill="black", width=2)
            for y in (70, 96, 122, 148, 174, 200):
                draw.line((50, y, 300, y), fill="black", width=2)
            path = Path(directory) / "incomplete.png"
            image.save(path)
            result = detect_grid(path, roi=(45,65,305,205),
                                 expected_vertical_lines=33,
                                 expected_horizontal_lines=8)
            self.assertFalse(result["layout_complete"])
            self.assertFalse(result["verified"])
            self.assertIn("VERTICAL_LINE_COUNT_MISMATCH", result["warnings"])

    def test_rotation_preserves_source(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow unavailable")
        with TemporaryDirectory() as directory:
            original = Path(directory) / "source.png"
            rotated = Path(directory) / "rotated.png"
            Image.new("RGB", (100, 200), "white").save(original)
            rotate_image(original, rotated, 90)
            self.assertEqual(Image.open(original).size, (100, 200))
            self.assertEqual(Image.open(rotated).size, (200, 100))


if __name__ == "__main__":
    unittest.main()
