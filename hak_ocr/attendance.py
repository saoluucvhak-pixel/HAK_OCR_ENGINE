"""Conservative attendance-table validation.

Cell values are OCR *candidates*, not approved payroll data. Blank != zero.
Coordinates are kept with each candidate for visual verification.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
import re

_NUMBER = re.compile(r"^(?:0|[1-9]\d*)(?:[.,]\d+)?$")

def parse_cell(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if not _NUMBER.fullmatch(text):
        return None
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None

@dataclass
class CellCandidate:
    row: int
    day: int
    raw: str
    bbox: list | None = None
    confidence: float | None = None
    approved: bool = False

def audit_attendance(rows, *, expected_days=30, tolerance="0"):
    """Rows: {employee_id, days:[{raw,bbox,confidence},...], total:{raw,...}}.

    Returns no inferred values. Totals matching alone never approves OCR.
    """
    if not isinstance(expected_days, int) or not 1 <= expected_days <= 31:
        raise ValueError("expected_days must be 1..31")
    limit = Decimal(tolerance)
    if limit < 0:
        raise ValueError("tolerance cannot be negative")
    reports = []
    for index, row in enumerate(rows):
        values = row.get("days", [])
        issues, cells, observed = [], [], []
        if len(values) != expected_days:
            issues.append("DAY_COUNT_MISMATCH")
        for day, cell in enumerate(values, 1):
            if not isinstance(cell, dict):
                raise TypeError("Each day must have OCR metadata")
            raw = str(cell.get("raw") or "").strip()
            value = parse_cell(raw)
            if raw and value is None:
                issues.append(f"INVALID_CELL_DAY_{day}")
            if raw == "":
                issues.append(f"BLANK_DAY_{day}")
            if value is not None:
                observed.append(value)
            confidence = cell.get("confidence")
            if confidence is None or not 0 <= float(confidence) <= 1:
                issues.append(f"UNCERTAIN_DAY_{day}")
            elif confidence < 0.85:
                issues.append(f"LOW_CONFIDENCE_DAY_{day}")
            cells.append(asdict(CellCandidate(index, day, raw, cell.get("bbox"), confidence)))
        reported = row.get("total", {})
        total_raw = str(reported.get("raw") or "").strip()
        total = parse_cell(total_raw)
        if total is None:
            issues.append("TOTAL_MISSING_OR_INVALID")
        if total is not None and (not observed or abs(sum(observed, Decimal(0)) - total) > limit):
            issues.append("TOTAL_MISMATCH")
        # A matching total with blank OCR cells is not sufficient evidence.
        reports.append({
            "employee_id": str(row.get("employee_id") or ""),
            "status": "NEEDS_REVIEW",
            "payroll_ready": False,
            "read_sum": str(sum(observed, Decimal(0))),
            "reported_total": total_raw,
            "numeric_cells": len(observed),
            "blank_cells": sum(c["raw"] == "" for c in cells),
            "expected_days": expected_days,
            "issues": issues,
            "cells": cells,
        })
    return {"schema_version": "1.0", "document_type": "bang_cham_cong",
            "status": "NEEDS_REVIEW", "rows": reports,
            "payroll_ready": False}
