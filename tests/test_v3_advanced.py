import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from hak_ocr.document_corners import detect_document_corners
from hak_ocr.table_structure import parse_table_structure
from hak_ocr.cell_consensus import compare_cell_batches

class V3AdvancedTests(unittest.TestCase):
    def test_corner_detection_synthetic_document(self):
        try:
            from PIL import Image,ImageDraw
            import cv2
        except ImportError:
            self.skipTest("Optional dependencies not installed")
        with TemporaryDirectory() as folder:
            image=Image.new("RGB",(600,450),"#777777")
            draw=ImageDraw.Draw(image)
            draw.polygon([(90,50),(530,65),(510,400),(70,380)],fill="white")
            path=Path(folder)/"test.png"
            image.save(path)
            result=detect_document_corners(path,min_area_ratio=.2)
            self.assertTrue(result["found"])
            self.assertEqual(len(result["corners"]),4)
            self.assertFalse(result["verified"])
    def test_corner_failure_closed(self):
        try:
            from PIL import Image
            import cv2
        except ImportError:
            self.skipTest("Optional dependencies not installed")
        with TemporaryDirectory() as folder:
            path=Path(folder)/"blank.png"
            Image.new("RGB",(400,300),"white").save(path)
            result=detect_document_corners(path)
            self.assertFalse(result["found"])
    def test_merged_header(self):
        data=parse_table_structure("<table><tr><th rowspan='2'>Tên</th><th colspan='2'>Ngày</th></tr><tr><td>01</td><td>02</td></tr></table>")
        self.assertEqual(data["column_count"],3)
        self.assertEqual(data["row_count"],2)
        self.assertEqual([(c["row"],c["col"]) for c in data["cells"]],
                         [(0,0),(0,1),(1,1),(1,2)])
    def test_no_table(self):
        with self.assertRaises(ValueError):
            parse_table_structure("nothing")
    def test_cell_disagreement(self):
        result=compare_cell_batches({"paddle":[{"bbox":[0,0,10,10],"text":"44"}],
                                     "smart":[{"bbox":[0,0,10,10],"text":"4"}]})
        self.assertEqual(result["disagreement_count"],1)
        self.assertFalse(result["approved"])
    def test_misaligned_cells_rejected(self):
        with self.assertRaises(ValueError):
            compare_cell_batches({"paddle":[{"bbox":[0,0,10,10],"text":"44"}],
                                  "smart":[{"bbox":[1,0,10,10],"text":"44"}]})
if __name__=="__main__":
    unittest.main()
