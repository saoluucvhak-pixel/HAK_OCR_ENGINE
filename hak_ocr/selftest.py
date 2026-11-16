"""Validate that a frozen Windows distribution can run without Internet.

This is not a substitute for a real GUI/document acceptance test.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib
import json
import os
import platform
import sys

from .config import resource_root
from .engine_config import setup_tesseract


def check_packaged_app(*,require_bundled: bool=False) -> dict:
    checks={}
    root=resource_root()
    exe=root/'vendor'/'tesseract'/'tesseract.exe'
    checks['bundled_tesseract_file']=exe.is_file()
    if require_bundled and not exe.is_file():
        checks['bundled_tesseract_required']=False
    try:
        path=setup_tesseract()
        import pytesseract
        available=set(pytesseract.get_languages(config=''))
        checks['tesseract_running']=bool(path)
        checks['tesseract_vie']='vie' in available
        checks['tesseract_eng']='eng' in available
    except Exception as exc:
        checks['tesseract_running']=False
        checks['tesseract_error']=f'{type(exc).__name__}: {exc}'
    try:
        from PIL import Image
        from io import BytesIO
        img=Image.new('RGB',(10,10),'white')
        out=BytesIO();img.save(out,format='PNG')
        checks['pillow_roundtrip']=Image.open(BytesIO(out.getvalue())).size==(10,10)
    except Exception as exc:checks['pillow_roundtrip']=False;checks['pillow_error']=str(exc)
    try:
        import fitz
        pdf=fitz.open();pdf.new_page(width=200,height=200);payload=pdf.tobytes();pdf.close()
        doc=fitz.open(stream=payload,filetype='pdf')
        checks['pdf_backend']=len(doc)==1
        doc.close()
    except Exception as exc:checks['pdf_backend']=False;checks['pdf_error']=str(exc)
    try:
        import pypdfium2
        checks['pdfium_import']=True
    except Exception as exc:checks['pdfium_import']=False;checks['pdfium_error']=str(exc)
    try:
        import PySide6.QtWidgets
        checks['qt_import']=True
    except Exception as exc:checks['qt_import']=False;checks['qt_error']=str(exc)
    try:
        from .storage import Repository
        with TemporaryDirectory(prefix='hak-ocr-selftest-') as folder:
            repo=Repository(Path(folder))
            repo.close()
            checks['sqlite_writable']=Path(folder,'hak_ocr.sqlite3').exists()
    except Exception as exc:checks['sqlite_writable']=False;checks['sqlite_error']=str(exc)
    required=('bundled_tesseract_file','tesseract_running','tesseract_vie','tesseract_eng',
              'pillow_roundtrip','pdf_backend','pdfium_import','qt_import','sqlite_writable') if require_bundled else (
              'tesseract_running','tesseract_vie','pillow_roundtrip','pdf_backend','pdfium_import','qt_import','sqlite_writable')
    return {'ok':all(checks.get(k,False) for k in required),
            'checks':checks,'required_checks':list(required),'platform':platform.platform(),
            'python':sys.version.split()[0],'frozen':bool(getattr(sys,'frozen',False)),
            'resources':str(root),'checked_at':datetime.now(timezone.utc).isoformat(),
            'offline_policy':'No model/network downloads at runtime'}
