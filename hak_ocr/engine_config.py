from __future__ import annotations
import os
from pathlib import Path
import shutil
import sys


def setup_tesseract() -> str:
    """Prefer private bundled Tesseract; otherwise use the user-installed one.

    Never downloads a model or opens a remote URL.
    """
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    bundled=root/'vendor'/'tesseract'/'tesseract.exe'
    if os.name=='nt' and bundled.is_file():
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd=str(bundled)
        data=bundled.parent/'tessdata'
        if data.is_dir():
            os.environ['TESSDATA_PREFIX']=str(data)
        os.environ['PATH']=str(bundled.parent)+os.pathsep+os.environ.get('PATH','')
        return str(bundled)
    return shutil.which('tesseract') or ''
