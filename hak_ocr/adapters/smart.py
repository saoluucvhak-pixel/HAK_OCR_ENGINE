"""Bridge to the existing HAK Smart OCR AI CLI without copying its source.

Source lives in LUONG_HAK/apps/hak-smart-ocr-ai on the OCR feature branch.
The bridge invokes its public CLI in a separate Python process.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from ..core import OCRPage

_DOC_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class SmartOCRAdapter:
    name = "hak-smart"

    def __init__(self, app_dir, *, python_executable=None, timeout=180, runner=None,
                 ocr_engine="tesseract"):
        directory = Path(app_dir).expanduser().resolve()
        if not (directory / "cli.py").is_file():
            raise ValueError("HAK Smart OCR AI cli.py not found in app_dir")
        if ocr_engine not in ("tesseract", "paddle", "hybrid"):
            raise ValueError("Unsupported HAK Smart OCR engine")
        if timeout <= 0 or timeout > 3600:
            raise ValueError("timeout must be between 1 and 3600 seconds")
        self.app_dir = directory
        self.python = python_executable or sys.executable
        self.timeout = timeout
        self.runner = runner or subprocess.run
        self.ocr_engine = ocr_engine

    def _call(self, args):
        completed = self.runner([self.python, str(self.app_dir / "cli.py"), *args],
                                cwd=str(self.app_dir), capture_output=True, text=True,
                                timeout=self.timeout, check=False)
        if completed.returncode != 0:
            # Avoid leaking document text, filenames or sensitive OCR output from stderr.
            raise RuntimeError("HAK Smart OCR AI command failed (details retained locally)")
        return completed.stdout

    def recognize(self, image_paths):
        pages = []
        with TemporaryDirectory(prefix="hak_smart_bridge_") as temp:
            data = Path(temp) / "data"
            for number, source in enumerate(image_paths, 1):
                log = self._call(["import-and-ocr", str(source), "--data", str(data),
                                  "--engine", self.ocr_engine])
                ids = re.findall(r"^DOCUMENT_ID\s+(\S+)\s*$", log, re.MULTILINE)
                if len(ids) != 1 or not _DOC_ID.fullmatch(ids[0]):
                    raise RuntimeError("Invalid document identifier from HAK Smart OCR AI")
                doc_id = ids[0]
                self._call(["export", doc_id, "--format", "json", "--data", str(data)])
                result_path = data / "exports" / (doc_id + ".json")
                result = json.loads(result_path.read_text(encoding="utf-8"))
                raw_pages = result.get("pages", [])
                if len(raw_pages) != 1:
                    raise RuntimeError("Unexpected page count in Smart OCR output")
                page = raw_pages[0]
                tables = [table.get("grid", []) for table in page.get("tables", [])]
                pages.append(OCRPage(number=number, text=str(page.get("text", "")),
                                     tables=tables))
        return pages
