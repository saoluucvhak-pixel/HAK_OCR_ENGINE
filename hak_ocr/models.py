from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Block:
    text: str
    bbox: list[float]      # normalized coordinates on original page, 0...1
    confidence: float | None = None
    engine: str = "tesseract"
    page: int = 0
    kind: str = "word"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Table:
    page: int
    bbox: list[float]
    grid: list[list[str]]
    cell_boxes: list[list[list[float]]]
    method: str = "opencv-grid-v1"
    table_id: str = ""
    # Suggested cell OCR is never a human verification. Metadata is stored
    # alongside the source-linked grid to make later review transparent.
    cell_suggestions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Field:
    key: str
    label: str
    raw: str
    value: str
    page: int
    bbox: list[float] | None
    confidence: float | None = None
    verified: bool = False
    source: str = "ocr"
    template_id: str = "generic"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Page:
    number: int
    width: int
    height: int
    text: str = ""
    blocks: list[Block] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    orientation: int = 0
    source: str = "ocr"
    warnings: list[str] = field(default_factory=list)
    geometry: dict = field(default_factory=dict)
    ocr_alternatives: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "number": self.number, "width": self.width, "height": self.height,
            "text": self.text, "blocks": [b.to_dict() for b in self.blocks],
            "tables": [t.to_dict() for t in self.tables],
            "orientation": self.orientation, "source": self.source,
            "warnings": self.warnings, "geometry": self.geometry,
            "ocr_alternatives": self.ocr_alternatives,
        }


@dataclass
class Result:
    document_id: str
    sha256: str
    filename: str
    document_type: str
    pages: list[Page] = field(default_factory=list)
    fields: list[Field] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "NEEDS_REVIEW"
    run_id: str = ""
    layout_extraction: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0", "document_id": self.document_id,
            "source_sha256": self.sha256, "filename": self.filename,
            "document_type": self.document_type, "status": self.status,
            "pages": [p.to_dict() for p in self.pages],
            "fields": [f.to_dict() for f in self.fields],
            "warnings": self.warnings, "run_id": self.run_id,
            "layout_extraction": self.layout_extraction,
        }
