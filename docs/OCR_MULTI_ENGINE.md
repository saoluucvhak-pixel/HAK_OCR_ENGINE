# HAK OCR multi-engine integration design

## Sources verified 22/11/2026
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — Apache-2.0; source commit `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`.
- [Umi-OCR](https://github.com/hiroi-sora/Umi-OCR) — MIT; source commit `83173efc4f4453b41223ea96d63d44534bf0505c`.
- [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) — MIT; source commit `37cf646758611a3b81f53863d1e91128a98d58b1`.
- Verify bundled model/plugin/runtime licenses separately. The main repository's license does not automatically govern every model, weight or third-party dependency.
- No third-party code, weights or installers have been copied into HAK by this change.

## Architecture and priorities
1. Existing native PDF text extraction (PyMuPDF) remains first choice where text is extractable.
2. Existing offline Tesseract and Electron JavaScript engines remain fallback.
3. PaddleOCR: optional structured-document, layout and table parsing engine; models must be installed/approved locally.
4. Umi-OCR: optional Windows operator-facing OCR application and alternative local CLI/loopback API adapter for screenshot/batch OCR. It can use Paddle-based plugins, so **do not count Umi and Paddle as independent models without checking the underlying plugin**.
5. Unlimited-OCR: optional heavyweight long-document / hard-layout parsing engine. Existing `hak_ocr/unlimited_engine.py` handles *experimental* checks only; validate explicit local model version and hardware. Unlimited-OCR 2's upstream docs describe inference via Transformers/SGLang and an A800 80 GB example; it is **not** an assumption that standard Windows PCs can run it.
6. Compare field and cell evidence, not just entire plain-text strings. Disagreements, absent confidence and uncertain text go to NEEDS_REVIEW.

## Proposed task pipeline
`IMPORT → CLASSIFY → SELECT_ENGINE → EXTRACT → NORMALIZE → VALIDATE → NEEDS_REVIEW → APPROVED → BUSINESS_IMPORT`.

At every stage preserve immutable source hash and metadata; use page and bounding-box evidence if available. Never auto-approve a payroll figure, weight, invoice or bank-related value.

## Contract
Use `hak_ocr.external_ocr_contract`: `OCRRequest`, `OCRResult`, `normalize_candidate`. This only validates candidates, does **not** run any external engine.
Candidate fields may include value, source_page, bbox and confidence (nullable); unknown confidence is not confidence=1.0.
Version each engine, model, plugin, preprocessing profile and output schema. Record actual underlying engine for Umi-OCR.

## Acceptance tests to implement
- Synthetic fixtures for all supported candidate engines and validation status.
- Actual offline adapter integration: missing binary/model, wrong version, timeout, malformed output, large files, Unicode Vietnamese, no network.
- Same document comparison: weigh-ticket number, kg vs tons, date, payee name, timesheet cells, subtotals and total sums.
- Handwriting, perspective, curved/warped tables, PDFs with text vs scans, blank cell vs 0.
- Reviewer authorization, edit and audit, hash-based deduplication, crash/retry and export/import gates.
- Windows EXE acceptance separately; no benchmark claim without corpus and measured precision/recall.

## Current maturity
This branch is a contract/design and synthetic-test preparation; runtime PaddleOCR/Umi-OCR/Unlimited-OCR integration has NOT been completed, and no OCR model or EXE has been validated as production-ready.
