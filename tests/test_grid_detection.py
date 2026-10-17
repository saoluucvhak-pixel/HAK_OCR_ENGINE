import unittest
from hak_ocr.grid_detection import _clusters

class GridUtilsTests(unittest.TestCase):
    def test_close_lines_merge(self):
        self.assertEqual(_clusters([20,21,22,60,61]),[21,60])
    def test_empty(self):
        self.assertEqual(_clusters([]),[])
if __name__=="__main__":unittest.main()
