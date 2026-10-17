import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from hak_ocr.perspective import _ordered,rectify_document
from hak_ocr.consensus import compare_proposals

class V3Tests(unittest.TestCase):
    def test_order_scrambled_corners(self):
        self.assertEqual(_ordered([[100,100],[0,0],[0,100],[100,0]]),
                         [(0.,0.),(100.,0.),(100.,100.),(0.,100.)])
    def test_reject_invalid_geometry(self):
        with self.assertRaises(ValueError):
            _ordered([[0,0],[1,1],[2,2],[3,3]])
    def test_warp_synthetic_image(self):
        try:
            from PIL import Image
            import cv2
        except ImportError:
            self.skipTest("Optional image dependencies unavailable")
        with TemporaryDirectory() as folder:
            src=Path(folder)/"source.png"
            dst=Path(folder)/"rectified.png"
            Image.new("RGB",(200,140),"white").save(src)
            report=rectify_document(src,dst,[[10,10],[180,15],[175,110],[15,115]])
            self.assertTrue(dst.exists())
            self.assertFalse(report["geometry_verified"])
            self.assertEqual(report["status"],"NEEDS_REVIEW")
            self.assertEqual(Image.open(src).size,(200,140))
            with self.assertRaises(ValueError):
                rectify_document(src,src,[[10,10],[180,15],[175,110],[15,115]])
    def test_disagreement_never_approves(self):
        result=compare_proposals({"paddle":"44","hak-smart":"4"})
        self.assertTrue(result["has_disagreement"])
        self.assertFalse(result["auto_approved"])
    def test_agreement_still_needs_review(self):
        result=compare_proposals({"paddle":"44","hak-smart":"44"})
        self.assertFalse(result["has_disagreement"])
        self.assertEqual(result["status"],"NEEDS_REVIEW")

if __name__=="__main__":
    unittest.main()
