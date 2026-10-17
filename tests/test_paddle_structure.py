import unittest
from pathlib import Path
from hak_ocr.adapters.paddle import PaddleAdapter, html_table_grid

class StubModel:
    def __init__(self, results):
        self.results = results
    def predict(self, path):
        return self.results

class TestPaddle(unittest.TestCase):
    def test_text(self):
        m = StubModel([{"res":{"rec_texts":["Số phiếu cân", "123"],"rec_scores":[0.9,0.8]}}])
        result = PaddleAdapter(model=m).recognize([Path("sample.png")])
        self.assertEqual(result[0].text, "Số phiếu cân\n123")
        self.assertAlmostEqual(result[0].confidence, 0.85)
    def test_table_structure(self):
        m = StubModel([{"res":{"parsing_res_list":[{"block_label":"text","block_content":"Phiếu cân"}],
                                  "table_res_list":[{"pred_html":"<table><tr><th>Số xe</th><th>KG</th></tr><tr><td>43A</td><td>12000</td></tr></table>"}]}}])
        result=PaddleAdapter(model=m,mode="structure").recognize([Path("sample.png")])
        self.assertEqual(result[0].tables, [[["Số xe","KG"],["43A","12000"]]])
        self.assertEqual(result[0].text,"Phiếu cân")
    def test_malformed_result_fails(self):
        with self.assertRaises(ValueError):
            PaddleAdapter(model=StubModel(["invalid"])).recognize([Path("sample.png")])
    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            PaddleAdapter(mode="unknown")
    def test_empty_results(self):
        result=PaddleAdapter(model=StubModel([]),mode="structure").recognize([Path("sample.png")])
        self.assertEqual(result[0].text,"")
        self.assertEqual(result[0].tables, [])
if __name__ == "__main__":
    unittest.main()
