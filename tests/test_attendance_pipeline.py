import unittest
from pathlib import Path
from unittest.mock import patch
from hak_ocr.attendance_pipeline import run_attendance_pilot
from hak_ocr.core import OCRPage

class FakeEngine:
    name="fake"
    def recognize(self, paths):
        # identity, two days, total
        text=["Mã thử", "1", "2", "3"]
        return [OCRPage(i+1, t, .99) for i,t in enumerate(text)]
class PipelineTests(unittest.TestCase):
    def test_pilot_with_fake_grid_and_engine(self):
        fakecells=[[{"row":0,"col":c,"bbox":[c*10,0,c*10+8,8],"image":FakeImage()}
                    for c in range(4)]]
        with patch("hak_ocr.attendance_pipeline.extract_cells",return_value=fakecells):
            report=run_attendance_pilot("fake.png", FakeEngine(),
                                        [0,10,20,30,40],[0,10],
                                        first_data_row=0,days=2,total_col=3)
        self.assertEqual(report["rows"][0]["read_sum"],"3")
        self.assertFalse(report["payroll_ready"])
        self.assertEqual(report["rows"][0]["employee_id"],"Mã thử")
    def test_missing_columns(self):
        with self.assertRaises(ValueError):
            run_attendance_pilot("fake.png",FakeEngine(),[0,1],[0,1],days=30)
class FakeImage:
    def save(self,path):
        Path(path).write_bytes(b"fake")

if __name__=="__main__":unittest.main()
