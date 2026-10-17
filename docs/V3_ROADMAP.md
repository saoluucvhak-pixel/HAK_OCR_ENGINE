# HAK OCR ENGINE V3.0 — shared library roadmap

## Implemented in this increment
- `hak_ocr.perspective.rectify_document`: explicit four-corner perspective correction, separate output, validation and output-size cap.
- `hak_ocr.consensus.compare_proposals`: compare two or more OCR text proposals, flag disagreements without auto-approval.
- Synthetic regression tests for geometry, source preservation and consensus.
- Existing adapters (HAK Smart OCR, PaddleOCR/PP-StructureV3, Unlimited-OCR), table grid, attendance checks and shared API remain intact.

## Not yet implemented or verified
- Automatic corner estimation and image-orientation scoring.
- AI table recognition beyond the current PP-StructureV3 adapter.
- Per-cell multi-engine consensus with coordinates and review UI.
- Real-model benchmark on HAK attendance photos and Vietnamese documents.
- Production packaging, full offline GPU/CPU validation and consumer application connectors.

## Safety and rollout
Do not upload actual payroll photos, personal IDs, account numbers or employee data to the public repository.
No other HAK app is modified; no automatic approval or data writeback.
All OCR outputs remain `NEEDS_REVIEW` pending source verification.
