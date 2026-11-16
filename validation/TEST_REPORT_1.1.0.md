# HAK Smart OCR AI 1.1.0 — Technical test report

## Environment

- Linux development environment, Python 3
- Running Tesseract with `vie` and `eng` models
- Pillow, OpenCV, PyMuPDF, pytesseract, pytest installed
- PaddleOCR, Docling, transformers and their model weights **not installed**
- PySide6 **not installed**; GUI has passed static Python compilation only

## Results

- Original 1.0.2 regression suite: **23 passed**
- New 1.1.0 unit/integration suite: **15 passed**
- Total: **38 passed**, no test failures (see reproducible command)
- `python -m compileall -q .`: passed
- CLI `advanced-check`: passed; correctly reports unavailable models
- Tesseract CLI on a supplied salary-payment screenshot: completed and returned
  an unverified OCR record. Several date/month strings were inaccurate, showing
  why this cannot be used automatically for payment or payroll.
- Additional 2-image real-data smoke (Tesseract, not advanced models): a chat
  screenshot processed in 0.91s (86 OCR blocks, 2 unverified text claims), and
  an attendance image in 1.17s (83 OCR blocks, 1 detected grid). These are
  pipeline signals, NOT accuracy measurements of the extracted claims/cells.

## Not tested on real model weights

- PaddleOCR prediction quality, Docling table extraction, handwritten OCR,
  UVDoc dewarping, GGUF semantic extraction
- Windows EXE installation / performance on CPU-only PC
- Real scanned-document end-to-end benchmarks across all 10 user samples

## Commands to reproduce

```powershell
py -3.11 -m pytest tests -q
py -3.11 -m compileall -q hak_ocr cli.py
py -3.11 cli.py advanced-check
```

All offline/model integrations must be re-run with correct weights and pinned
versions on a clean Windows PC before calling the product production-ready.
