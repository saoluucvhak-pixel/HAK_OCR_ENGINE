# HAK Smart OCR — Offline Model Layout (no weights bundled)

The source ZIP intentionally contains **NO machine-learning weights**, no private
employee document images and no credentials. Install legally obtained, compatible
model artifacts *on an offline staging machine* under these subdirectories:

- `paddle_detection/` — compatible PaddleOCR 3.x detection model.
- `paddle_recognition/` — recognition model **proven to support Vietnamese** (benchmark it).
- `docling/` — fully prefetched Docling `artifacts_path` directory for the tested version.
- `handwriting/` — local transformers `config.json`, processor/tokenizer, weights.
  English TrOCR checkpoints are **not validated for Vietnamese handwriting**.
- `doc_unwarp/` — UVDoc inference model for curved-page preview only.
- `evidence_llm/` — optional GGUF model and a compatible local llama-cpp-python installation.

Keep these under `vendor/models` for packaged applications, or set
`HAK_OCR_MODELS_DIR` to an absolute path to a model directory outside the EXE.
For Docling conversion, remote services are disabled and model artifacts are
mandatory. For PaddleOCR/UVDoc, no additional orientation model is silently
loaded: the corresponding preprocessing options are explicitly turned off.

A directory containing only this README is NOT a usable model.
If a model is missing, the app reports an error instead of silently downloading.

### Important provenance boundaries

- `--perspective` uses OpenCV planar quad only and supports source-linked boxes.
- UVDoc `unwarp-preview` may straighten curved pages, but inverse pixel geometry
  is **not available** here: output is an **unverified derivative**, not original
  source, and must be reviewed/re-imported.
- Docling provides supplementary markdown/layout. The app does not claim its
  markdown has exact clickable cell coordinates.
- Handwriting models and local LLM suggestions are never auto-confirmed.
