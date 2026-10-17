import unittest
from hak_ocr.attendance import audit_attendance

def cells(value="1", conf=.98):
    return [{"raw": value, "confidence": conf, "bbox": [x, 0, x+1, 1]} for x in range(30)]

class AttendanceTests(unittest.TestCase):
    def test_matching_total_still_needs_review(self):
        result=audit_attendance([{"employee_id": "fake", "days": cells(), "total": {"raw":"30"}}])
        row=result["rows"][0]
        self.assertEqual(row["read_sum"], "30")
        self.assertEqual(row["issues"], [])
        self.assertFalse(row["payroll_ready"])
    def test_blank_never_automatic_zero(self):
        values=cells()
        values[2]={"raw":"","confidence":None}
        row=audit_attendance([{"days":values, "total":{"raw":"29"}}])["rows"][0]
        self.assertEqual(row["blank_cells"], 1)
        self.assertIn("BLANK_DAY_3",row["issues"])
        self.assertEqual(row["read_sum"],"29")
    def test_number_mismatch(self):
        row=audit_attendance([{"days":cells(), "total":{"raw":"44"}}])["rows"][0]
        self.assertIn("TOTAL_MISMATCH",row["issues"])
    def test_unknown_not_a_number(self):
        values=cells()
        values[0]["raw"]="l"
        row=audit_attendance([{"days": values,"total":{"raw":"29"}}])["rows"][0]
        self.assertIn("INVALID_CELL_DAY_1", row["issues"])
    def test_low_confidence(self):
        row=audit_attendance([{"days":cells(conf=.4),"total":{"raw":"30"}}])["rows"][0]
        self.assertIn("LOW_CONFIDENCE_DAY_1",row["issues"])
if __name__=="__main__":unittest.main()
