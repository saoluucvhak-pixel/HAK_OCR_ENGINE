from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from hak_ocr.core import OCRPage, OCRService
from hak_ocr.adapters.unlimited import UnlimitedAdapter

class FakeAdapter:
    name="fake"
    def recognize(self, images): return [OCRPage(number=i+1, text="Số phiếu 123") for i, _ in enumerate(images)]

class Tests(unittest.TestCase):
    def test_document(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"sample.png"; p.write_bytes(b"fixture")
            r=OCRService({"fake":FakeAdapter()}).process(p,"fake")
            self.assertEqual(r.text,"Số phiếu 123")
            self.assertEqual(len(r.source_sha256),64)
    def test_explicit_engine(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"sample.png"; p.write_bytes(b"fixture")
            with self.assertRaises(ValueError): OCRService({}).process(p,"unlimited")
    def test_no_remote(self):
        for endpoint in ("https://example.com", "http://192.168.1.1:10000", "http://localhost:10000"):
            with self.assertRaises(ValueError): UnlimitedAdapter(endpoint=endpoint)
    def test_local_allowed(self):
        self.assertEqual(UnlimitedAdapter().name,"unlimited")
    def test_extension(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"malware.exe"; p.write_bytes(b"exe")
            with self.assertRaises(ValueError): OCRService({"fake":FakeAdapter()}).process(p,"fake")

if __name__ == "__main__": unittest.main()
