"""Vendor-neutral OCR service: no silent fallback, no document uploads."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
import hashlib

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".pdf"}

@dataclass
class OCRPage:
    number: int
    text: str
    confidence: float | None = None
    tables: list = field(default_factory=list)

@dataclass
class OCRResult:
    engine: str
    source_sha256: str
    pages: list[OCRPage]
    warnings: list[str] = field(default_factory=list)
    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)
    def to_dict(self) -> dict:
        return {"schema_version": "1.0", "engine": self.engine, "source_sha256": self.source_sha256,
                "pages": [vars(page) for page in self.pages], "text": self.text, "warnings": self.warnings}

class OCREngine(Protocol):
    name: str
    def recognize(self, image_paths: list[Path]) -> list[OCRPage]: ...

class OCRService:
    def __init__(self, engines: dict[str, OCREngine], *, max_file_bytes: int = 50_000_000, max_pages: int = 50):
        self.engines = engines
        self.max_file_bytes = max_file_bytes
        self.max_pages = max_pages
    def process(self, file: str | Path, engine: str) -> OCRResult:
        from .pdf import pages_as_images
        source = Path(file).resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in ALLOWED_EXT:
            raise ValueError("Unsupported document type")
        if source.stat().st_size > self.max_file_bytes:
            raise ValueError("Document exceeds configured file limit")
        if engine not in self.engines:
            raise ValueError(f"Engine unavailable: {engine}")
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        with pages_as_images(source, max_pages=self.max_pages) as image_paths:
            pages = self.engines[engine].recognize(image_paths)
        if len(pages) != len(image_paths):
            raise RuntimeError("OCR engine returned wrong number of pages")
        return OCRResult(engine=engine, source_sha256=digest, pages=pages)
