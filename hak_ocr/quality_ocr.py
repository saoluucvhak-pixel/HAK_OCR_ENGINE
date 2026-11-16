"""Quality-first offline Tesseract OCR for photographed Vietnamese documents.

The original image stays unchanged. All OCR variants preserve source-coordinate
mapping, and predictions remain unverified until human review.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output

from .models import Block


def _images_for_ocr(image: Image.Image, *, detailed: bool):
    """Yield (label, image, resize scale); variants are temporary OCR views."""
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    yield "clahe", Image.fromarray(enhanced), 1.0
    if not detailed:
        return
    yield "original", Image.fromarray(gray), 1.0
    # In photos of small ruled forms Otsu often destroys thin type; use a
    # local threshold on a *separate* view, never on the original pixels.
    height, width = gray.shape
    if width * height > 12_000_000:
        return
    window = 31 if min(height, width) >= 70 else 15
    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, window, 13)
    scale = 1.5 if min(width, height) < 1300 and width * height < 3_000_000 else 1.0
    if scale != 1.0:
        binary = cv2.resize(binary, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_CUBIC)
    yield "adaptive-bw", Image.fromarray(binary), scale


def _recognize_variant(image: Image.Image, width: int, height: int, lang: str,
                       scale: float, *, timeout: int = 30) -> tuple[list[Block], float]:
    data = pytesseract.image_to_data(
        image, lang=lang, output_type=Output.DICT,
        config="--psm 11 --oem 1", timeout=timeout)
    words = []
    score = 0.0
    for i, value in enumerate(data.get("text", [])):
        txt = str(value).strip()
        if not txt:
            continue
        try:
            conf = float(data["conf"][i])
            left = float(data["left"][i]) / scale
            top = float(data["top"][i]) / scale
            right = (float(data["left"][i]) + float(data["width"][i])) / scale
            bottom = (float(data["top"][i]) + float(data["height"][i])) / scale
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if not np.isfinite(conf) or conf < 0:
            continue
        x0 = max(0.0, min(1.0, left / width))
        y0 = max(0.0, min(1.0, top / height))
        x1 = max(0.0, min(1.0, right / width))
        y1 = max(0.0, min(1.0, bottom / height))
        if x1 <= x0 or y1 <= y0:
            continue
        words.append(Block(txt, [x0, y0, x1, y1], conf, "tesseract", 0))
        # Prefer credible text volume, not only the highest confidence token.
        # This is a heuristic for variant selection, NOT calibrated accuracy.
        chars = min(len(txt), 16)
        score += chars * (min(conf, 100.0) / 100.0) ** 1.4
    return words, score


def recognize_quality(image: Image.Image, lang: str, *,
                      detailed: bool = True) -> tuple[list[Block], dict]:
    """Evaluate OCR preprocessing variants and select a candidate transcription.

    Errors in a secondary variant do not discard a valid primary result.
    Returns diagnostics for a user-facing quality warning.
    """
    original_w, original_h = image.size
    if original_w < 16 or original_h < 16:
        return [], {"selected": "none", "candidates": [], "needs_review": True}
    attempts = []
    best_words: list[Block] = []
    best_score = -1.0
    best_name = "none"
    for name, prepared, scale in _images_for_ocr(image, detailed=detailed):
        try:
            words, score = _recognize_variant(prepared, original_w, original_h,
                                              lang, scale)
        except (RuntimeError, pytesseract.TesseractError, OSError) as exc:
            attempts.append({"variant": name, "error": type(exc).__name__})
            continue
        attempts.append({"variant": name, "words": len(words), "score": round(score, 2)})
        if score > best_score:
            best_score = score
            best_name = name
            best_words = words
    if best_score < 0:
        raise RuntimeError("Không thể đọc bằng Tesseract ở bất kỳ chế độ xử lý ảnh nào.")
    return best_words, {
        "selected": best_name,
        "candidates": attempts,
        "needs_review": True,
    }
