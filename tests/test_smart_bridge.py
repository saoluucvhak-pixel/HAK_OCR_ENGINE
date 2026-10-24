import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from hak_ocr.adapters.smart import SmartOCRAdapter
from hak_ocr.core import OCRService


class TestSmartBridge(unittest.TestCase):
    def test_bridge_without_real_ocr(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / "app"
            app.mkdir()
            (app / "cli.py").write_text("# fixture", encoding="utf-8")
            picture = root / "sample.png"
            picture.write_bytes(b"fixture")
            calls = []
            def fake_run(cmd, **options):
                calls.append(cmd)
                args = cmd[2:]
                data = Path(args[args.index("--data") + 1])
                if args[0] == "export":
                    dest = data / "exports"
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / "sample1.json").write_text(json.dumps({
                        "pages": [{"text": "Bảng chấm công", "tables": [{"grid": [["Họ tên", "Ngày"]]}]}]
                    }), encoding="utf-8")
                    return SimpleNamespace(returncode=0, stdout="")
                return SimpleNamespace(returncode=0, stdout="DOCUMENT_ID sample1\n")
            adapter = SmartOCRAdapter(app, runner=fake_run)
            result = OCRService({"hak-smart": adapter}).process(picture, "hak-smart")
            self.assertEqual(result.pages[0].text, "Bảng chấm công")
            self.assertEqual(result.pages[0].tables[0], [["Họ tên", "Ngày"]])
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][2], "import-and-ocr")

    def test_failure_does_not_expose_stderr(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "cli.py").touch()
            def failing(cmd, **opts):
                return SimpleNamespace(returncode=1, stdout="", stderr="PRIVATE EMPLOYEE DATA")
            adapter = SmartOCRAdapter(root, runner=failing)
            with self.assertRaises(RuntimeError) as caught:
                adapter.recognize([root / "sample.png"])
            self.assertNotIn("PRIVATE EMPLOYEE DATA", str(caught.exception))

    def test_missing_existing_app(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                SmartOCRAdapter(folder)


if __name__ == "__main__":
    unittest.main()
