# HAK Smart OCR AI 1.1.0 — Quickstart (source build, not a Windows installer)

This is an **advanced code release**, not a confirmed working Windows EXE.

## Base OCR first

On a Windows workstation with Python 3.11 and Tesseract `vie` and `eng` already
installed or privately bundled:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe run.py
```

`wheelhouse` must contain all matching Windows wheels. No internet is needed.
For source development where Internet is allowed *only on a separate preparation
machine*, resolve dependencies and models THERE and transfer them offline.

## Installing advanced models offline

Install all advanced Python dependencies from wheelhouse, then copy the compatible
inference weights to `vendor/models/<model role>/` (see `vendor/models/README.md`).
Or set environment variable `HAK_OCR_MODELS_DIR` to the equivalent local path.

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements-advanced.txt
.\.venv\Scripts\python.exe cli.py advanced-check
.\.venv\Scripts\python.exe cli.py import-and-ocr sample.jpg --engine hybrid --perspective
.\.venv\Scripts\python.exe cli.py import-and-ocr sample.pdf --docling
.\.venv\Scripts\python.exe cli.py evidence-claims DOCUMENT_ID
.\.venv\Scripts\python.exe cli.py handwriting handwritten_crop.png
.\.venv\Scripts\python.exe cli.py unwarp-preview curved_photo.png new_image_for_review.png
```

If an advanced model is missing, the corresponding operation fails with a local
error; it does not silently download it.

## Using the GUI

- Import images and PDF; choose Tesseract, local PaddleOCR, or hybrid mode.
- Optionally enable **Sửa phối cảnh** (planar only) or **Docling PDF**.
- In Review Studio, drag to select a handwritten region and select **Đọc chữ
  viết tay (vùng chọn)**. It saves an unverified candidate field.
- For curved photos choose **Xem trang cong (UVDoc)**. The output has no exact
  inverse bbox mapping; save a new derivative PNG and review/reimport.
- For chat screenshots, read and correct OCR text in **Văn bản OCR**, press **Lưu
  văn bản OCR đã hiệu đính**, then **Phân tích tin nhắn OCR** in **Bằng chứng**.
  Optionally turn on the locally installed GGUF model.
- Review claims; CONFIRMED means the text suggestion was checked, **not** that a
  payroll adjustment is authorized. Use manual evidence links to compare sources.

## Never bypass review for sensitive fields

Wages, dates, bank account numbers, identity numbers, signatures, workdays,
attendance and allowances are **not automatically approved** by the AI.

## Windows build

- Base: `scripts/build_windows.ps1`
- Advanced models: `scripts/build_windows_advanced.ps1`
- Neither builder has been tested in the current Linux environment. The
  advanced builder may require adjustments to the actual Python wheels and
  PyInstaller hooks on a Windows clean room. Validate model SHA256 and license.
