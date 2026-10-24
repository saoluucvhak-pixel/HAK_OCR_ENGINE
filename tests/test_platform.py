import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from hak_ocr.core import OCRPage
from hak_ocr.platform import HAKOCRPlatform, PlatformConfig
from hak_ocr.contracts import run_request,validate_request

class FakeEngine:
    def recognize(self, images):
        return [OCRPage(i+1,"TEST PAGE",0.9) for i,_ in enumerate(images)]

class PlatformTest(unittest.TestCase):
    def test_api_for_all_hak_consumers(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/"scan.png"
            source.write_bytes(b"fake image fixture")
            platform=HAKOCRPlatform({"mock":FakeEngine()},PlatformConfig(default_engine="mock"))
            for kind in ("bang_cham_cong","phieu_can","hoa_don","hop_dong","generic"):
                result=run_request(platform,{"api_version":"1.0","source_path":str(source),
                                             "engine":"mock","document_type":kind})
                self.assertEqual(result["ocr"]["text"],"TEST PAGE")
                self.assertEqual(result["status"],"NEEDS_REVIEW")
                self.assertFalse(result["approved"])
                self.assertFalse(result["payroll_ready"])

    def test_registered_not_equal_ready(self):
        info=HAKOCRPlatform({"mock":FakeEngine()}).health()
        self.assertEqual(info["engines"][0]["status"],"NOT_TESTED")
        self.assertFalse(info["engines"][0]["offline_verified"])

    def test_no_silent_fallback(self):
        platform=HAKOCRPlatform({"mock":FakeEngine()})
        with self.assertRaises(ValueError):
            platform.recognize("anything.png",engine="missing")

    def test_no_approval_forgery(self):
        with self.assertRaises(ValueError):
            validate_request({"api_version":"1.0","source_path":"image.png",
                              "engine":"paddle","document_type":"phieu_can","approved":True})

    def test_unsupported_version(self):
        with self.assertRaises(ValueError):
            validate_request({"api_version":"2.0","source_path":"x",
                              "engine":"paddle","document_type":"generic"})

    def test_duplicate_registration(self):
        p=HAKOCRPlatform({"mock":FakeEngine()})
        with self.assertRaises(ValueError):
            p.register("mock",FakeEngine())

    def test_config_limits(self):
        with self.assertRaises(ValueError):
            PlatformConfig(max_pages=0)

if __name__=="__main__":unittest.main()
