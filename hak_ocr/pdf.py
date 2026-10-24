"""Temporary PDF rasterization; cleans all intermediate images."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

@contextmanager
def pages_as_images(source: Path, *, max_pages=50, dpi=200):
    if source.suffix.lower() != ".pdf":
        yield [source]
        return
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF processing requires pip install pymupdf") from exc
    with fitz.open(source) as doc:
        if not doc.page_count or doc.page_count > max_pages:
            raise ValueError("PDF page count outside configured limits")
        with TemporaryDirectory(prefix="hak_ocr_") as temp:
            paths = []
            for i, page in enumerate(doc):
                dest = Path(temp) / f"page_{i+1:04d}.png"
                page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72)).save(dest)
                paths.append(dest)
            yield paths
