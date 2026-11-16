# HAK Smart OCR AI — Changes from 1.0.2 to 1.1.0 (code release)

## Implemented and exercised with unit/integration tests

1. Optional PaddleOCR 3.x adapter with local detection and recognition model
   paths. Parses `rec_texts`, `rec_scores`, and `rec_polys/rec_boxes`.
2. Optional hybrid candidate comparison, non-destructive disagreements.
3. Optional Docling PDF converter with explicit local `artifacts_path` and remote
   services disabled. Its markdown output is supplementary, not source bbox.
4. Conservative planar perspective correction and consistent preview warp.
5. Optional local TrOCR handwriting inference for selected image crop, with
   unverified field candidates and explicit review requirements.
6. Optional UVDoc local page-curvature unwarping for unverified preview/export.
7. Deterministic Vietnamese evidence extraction for messages about missed work,
   days, periods, fingerprint corrections, with traceable snippets.
8. Optional local GGUF-assisted extraction; accepts only quotes found verbatim
   in the OCR input and never records approved payroll changes.
9. Evidence proposals persisted in SQLite with `PROPOSED`, `CONFIRMED` (text
   content only), `REJECTED`; no automatic payroll or timesheet editing.
10. A separate human-corrected OCR text record that preserves the raw OCR text;
    superseded OCR runs do not inherit corrections of older runs.
11. New UI controls for engine selection, Docling, perspective correction, manual
    handwriting selection, UVDoc preview, OCR conflicts, and evidence review.
12. New CLI: `advanced-check`, `--engine`, `--docling`, `--perspective`,
    `evidence-claims`, `handwriting`, `unwarp-preview`.

## Not completed / not claimed

- Actual PaddleOCR/Docling/TrOCR/UVDoc/LLM model inference: the compatible model
  libraries and weights are NOT available in the current environment. Adapters
  were tested with mock interfaces only.
- Vietnamese handwritten text accuracy is unknown; model training required.
- Curved-page inverse geometry / approved cell-to-original mapping is not solved.
- The semantic evidence extractor supports only limited patterns, and OCR quality
  affects results. Manual confirmation remains mandatory.
- Windows EXE, GUI runtime and installer were NOT built/tested on Windows.
- The selected Python dependency versions are not yet locked by a Windows test.
- No personal employee images, chats, model weights or credentials included.

## Migration

SQLite tables `page_text_corrections` and `evidence_claims` are created on the
next startup. Existing source files, corrections, reviewed tables and learning
rules remain in the original database. Backup before upgrading as usual.
