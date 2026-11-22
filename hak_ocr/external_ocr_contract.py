"""Pure schema for candidate results from optional offline OCR engines.

This module does not execute processes or download models. Candidates always
require review; production adapters must be implemented and validated separately.
"""
from dataclasses import dataclass, field
from typing import Any, Mapping
import re

SUPPORTED_ENGINES = frozenset({"paddleocr", "umi-ocr", "unlimited-ocr"})
NEEDS_REVIEW = "NEEDS_REVIEW"

@dataclass(frozen=True)
class OCRRequest:
    task_id: str
    document_sha256: str
    local_path: str
    document_type: str
    schema_version: str = "1"

    def __post_init__(self):
        if not isinstance(self.task_id, str) or not 1 <= len(self.task_id.strip()) <= 128:
            raise ValueError("task_id is required")
        if not isinstance(self.document_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", self.document_sha256):
            raise ValueError("invalid document SHA256")
        if not isinstance(self.local_path, str) or not self.local_path.strip():
            raise ValueError("local_path required")
        if not isinstance(self.document_type, str) or not self.document_type.strip():
            raise ValueError("document_type required")

@dataclass(frozen=True)
class OCRCandidate:
    task_id: str
    engine: str
    version: str
    document_sha256: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    tables: tuple = ()
    warnings: tuple = ()
    review_status: str = NEEDS_REVIEW

    def __post_init__(self):
        if self.engine not in SUPPORTED_ENGINES:
            raise ValueError("unsupported engine")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("engine version required")
        if self.review_status != NEEDS_REVIEW:
            raise ValueError("OCR candidates cannot be auto-approved")
        if not isinstance(self.document_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", self.document_sha256):
            raise ValueError("invalid source hash")

def normalize_candidate(request: OCRRequest, engine: str, version: str, fields=None, tables=(), warnings=()):
    return OCRCandidate(request.task_id, engine, version, request.document_sha256, dict(fields or {}), tuple(tables), tuple(warnings))
