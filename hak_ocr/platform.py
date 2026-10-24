"""Stable, offline-first facade for future HAK application integrations.

Applications call a single API. Engines are injected, never silently installed,
downloaded or started. OCR proposals are *never* payroll/accounting approval.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .core import OCRService
from .attendance import audit_attendance


@dataclass(frozen=True)
class PlatformConfig:
    default_engine: str = "hak-smart"
    max_file_bytes: int = 50_000_000
    max_pages: int = 50

    def __post_init__(self):
        if not isinstance(self.default_engine, str) or not self.default_engine:
            raise ValueError("default_engine required")
        if not 0 < self.max_file_bytes <= 250_000_000:
            raise ValueError("invalid max_file_bytes")
        if not 0 < self.max_pages <= 200:
            raise ValueError("invalid max_pages")


class HAKOCRPlatform:
    """Versioned facade, independent of payroll/kho/HDMB app implementations."""

    def __init__(self, engines=None, config=None):
        self.config = config or PlatformConfig()
        self._engines = {}
        for name, engine in (engines or {}).items():
            self.register(name, engine)

    def register(self, name, engine):
        if not isinstance(name, str) or not name or not callable(getattr(engine, "recognize", None)):
            raise ValueError("Engine must implement recognize(image_paths)")
        if name in self._engines:
            raise ValueError("Engine already registered")
        self._engines[name] = engine

    def engines(self):
        return sorted(self._engines)

    def health(self):
        """Describe *registration* only; never report real model readiness without probing."""
        return {"schema_version":"1.0", "status":"CONFIGURED" if self._engines else "NOT_CONFIGURED",
                "engines": [{"name":name,"status":"NOT_TESTED","offline_verified":False}
                            for name in self.engines()],
                "read_only_by_default":True}

    def recognize(self, source, *, engine=None, document_type="generic"):
        chosen = engine or self.config.default_engine
        if chosen not in self._engines:
            raise ValueError("Selected engine is not registered")
        if not isinstance(document_type,str) or not document_type.strip():
            raise ValueError("document_type required")
        service = OCRService(self._engines, max_file_bytes=self.config.max_file_bytes,
                             max_pages=self.config.max_pages)
        data = service.process(Path(source), chosen).to_dict()
        return {"api_version":"1.0", "document_type":document_type,
                "status":"NEEDS_REVIEW", "approved":False, "payroll_ready":False,
                "ocr":data}

    def validate_attendance(self, rows, *, expected_days=30):
        """Post-OCR arithmetic audit; never authorizes posting to another HAK app."""
        return audit_attendance(rows, expected_days=expected_days)
