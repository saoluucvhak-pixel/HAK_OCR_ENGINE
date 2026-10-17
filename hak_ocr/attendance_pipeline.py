"""Conservative attendance OCR pilot for aligned grid images.

No inferred employee names, automatic payroll approval or network requests.
Provide the verified grid coordinates, first data row and column positions.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from .table_grid import extract_cells, save_crops
from .attendance import audit_attendance

def run_attendance_pilot(image, engine, xs, ys, *, first_data_row=1,
                         identifier_col=0, first_day_col=1, days=30,
                         total_col=None):
    if total_col is None:
        total_col = first_day_col + days
    if not isinstance(days, int) or not 1 <= days <= 31:
        raise ValueError("days must be 1..31")
    if len(xs)-1 <= max(identifier_col, total_col, first_day_col+days-1):
        raise ValueError("Grid does not contain expected columns")
    if first_data_row < 0 or first_data_row >= len(ys)-1:
        raise ValueError("No data rows")
    cells = extract_cells(image, list(xs), list(ys), padding=1)
    targets = []
    for row_idx in range(first_data_row, len(cells)):
        targets.extend(cells[row_idx][col] for col in
                       [identifier_col, *range(first_day_col, first_day_col+days), total_col])
    with TemporaryDirectory(prefix="hak_attendance_") as temp:
        paths = []
        for i, cell in enumerate(targets):
            path = Path(temp) / f"cell_{i:05d}.png"
            cell["image"].save(path)
            paths.append(path)
        recognized = engine.recognize(paths)
    if len(recognized) != len(targets):
        raise RuntimeError("Engine returned wrong number of cells")
    by_position = {(cell["row"],cell["col"]):
                   {"raw": str(page.text).strip(),
                    "confidence": page.confidence, "bbox": cell["bbox"]}
                   for cell,page in zip(targets,recognized)}
    rows = []
    for r in range(first_data_row,len(cells)):
        rows.append({
            # OCR name is provisional and never an identity match
            "employee_id": by_position[(r,identifier_col)]["raw"],
            "days": [by_position[(r,c)] for c in range(first_day_col,first_day_col+days)],
            "total": by_position[(r,total_col)]})
    report = audit_attendance(rows, expected_days=days)
    report["engine"] = engine.name
    report["source_image"] = Path(image).name
    report["grid_verified"] = False
    report["warnings"] = ["Grid alignment and staff identities require manual verification"]
    return report
