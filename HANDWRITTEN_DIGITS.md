# Offline handwritten digit model

This branch adds actual pretrained CNN weights and deterministic JavaScript inference. It is not a second wrapper around Tesseract and it requires neither Python, GPU, ONNX Runtime nor a network connection at application runtime.

## Scope

The model classifies **one isolated handwritten digit 0–9**. It does not read Vietnamese names, cursive words, connected multi-digit strings, decimal notation or whole pages. Multi-character crops and blank cells are withheld instead of being forced to a digit. A crop suggestion is never an approval, and the Tesseract text/confidence remain intact until a person explicitly chooses the suggestion.

## Source

- ONNX model zoo `mnist-12.onnx`, upstream commit `4c46cd00fbdb7cd30b6c1c17ab54f2e1f4f7b177`.
- Source: https://github.com/onnx/models/tree/4c46cd00fbdb7cd30b6c1c17ab54f2e1f4f7b177/validated/vision/classification/mnist
- Original model SHA256: `5c688690f8bacf667d4c2074af5ad0646ca328d7ab03eccf944a65b320171bdd`.
- The original CNN weights were converted losslessly to little-endian float32 arrays in JSON. The model's MIT license and upstream attribution are preserved in `js/ocr/models/NOTICE.md` and `LICENSE-CNTK-MIT.txt`.

## Measured results

Independent official MNIST test split, 10,000 handwritten images, no fitting or threshold tuning on that test split:

- Canonical 28×28 input: **9890/10000 (98.90%)**.
- Paper-crop normalization path: **9783/10000 (97.83%)**, counting unsupported crops as failures; 9930 crops supported.
- Fixed score >= 0.95 and margin >= 0.8 produced 9587 candidate suggestions, of which 30 were wrong. Scores are uncalibrated softmax values, not field accuracy. This is why suggestions require a human decision.
- JavaScript top-1 outputs match ONNX Runtime on 100 held-out reference images; maximum logit difference `0.000011444091796875`.
- Local benchmark for both paths: 74690 ms / 10000 images. This is a model benchmark, not whole-document processing time or performance on a user's machine.

The dataset contains real handwritten digits from MNIST, **not real employee documents**. These results do not establish accuracy on company timesheets, camera photos, Vietnamese handwriting or names. The report is `js/reports/handwriting-mnist-test.json`.

## Use and validate

```js
const H = require('./js/main/handwritten-digits.js');
const recognizer = H.create(require('./js/ocr/models/mnist-cnn.json'));
const result = H.addCandidate({ text: originalText, conf: originalScore },
  { w: cropWidth, h: cropHeight, data: grayscaleOnWhite }, recognizer);
// result.text and result.conf are unchanged. Inspect result.handwriting.
```

Run `node --test js/tests/unit/handwritten-digits.test.js`.
The 100 test fixtures are from the official MNIST test split, attributed to Yann LeCun and Corinna Cortes and distributed under CC BY-SA 3.0. See `js/tests/fixtures/handwriting/NOTICE.md`.

For reproduction, download the pinned ONNX model and the official `mnist.npz` into a separate build-only directory, run `python js/scripts/export-handwriting-model.py <directory>` with NumPy/onnx/onnxruntime installed, then run `node js/scripts/benchmark-handwriting.cjs <directory>/mnist-test.bin`. Dataset and model SHA256 checks are mandatory. No company image, backup or private model is part of this repository.
# Separated decimal proposals and acceptance tooling

The current feature branch adds conservative column segmentation for decimal crops with an explicit small baseline separator and separated full-height digits. It never invents a missing separator, leaves touching/ambiguous glyphs for manual review, and preserves original OCR. This is a segmentation extension using the existing fixed MNIST weights, not a newly trained handwriting model. Synthetic composites do not demonstrate real-document decimal accuracy.

`js/scripts/ocr-acceptance.cjs` evaluates private, locally labeled per-cell JSON (schema 1). It refuses incomplete labels, duplicate row/day keys and group leakage across splits, excludes training/validation pages, and reports only aggregate counts. `READY_FOR_HUMAN_SIGNOFF` requires declared real-private evidence, >=30 test pages, >=3000 cells, both clear/hard pages, zero alignment failures and >=99% clear-cell accuracy. It is not automatic acceptance: human review of workload, suggestion errors, offline Windows behavior and import/payroll regression remains required.

