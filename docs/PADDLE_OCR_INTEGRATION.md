# PaddleOCR integration in HAK OCR CENTER

Upstream source: https://github.com/PaddlePaddle/PaddleOCR

## Features
- `PaddleAdapter(mode="text")`: PaddleOCR 3.x OCR recognition, text and average recognizer confidence.
- `PaddleAdapter(mode="structure")`: PP-StructureV3 for document parsing and simple HTML table grids.
- Automatic PDF page rasterization remains in `hak_ocr/pdf.py`. One `OCRPage` per page, compatible with the central HAK data contract.
- Engines `hak-smart`, `paddle`, and `unlimited` remain independent; no upstream PaddleOCR source has been copied.

## Example
```python
from hak_ocr.core import OCRService
from hak_ocr.adapters import PaddleAdapter

engine = PaddleAdapter(mode="structure", model_options={"device": "cpu"})
result = OCRService({"paddle": engine}).process("example.pdf", "paddle")
print(result.to_dict())
```

Requires PaddlePaddle runtime and `paddleocr` with **doc-parser** extra for PP-StructureV3. See upstream installation guide for the exact combination of Python/PaddlePaddle/CPU/GPU/CUDA versions.

**Offline limitation**: default Paddle pipelines can download model weights. For production offline deployments, install and pin exact local models and pass supported `*_model_dir` paths explicitly through `model_options`. Test an isolated machine with networking disabled. We do not claim offline compliance merely because `device="cpu"` is selected.

## Known limits
- HTML table parsing captures plain cell text, but does not reconstruct merged-cell geometry or cell coordinates.
- Recognized values are `NEEDS_REVIEW` until source-based HAK validation and human approval.
- No accuracy benchmarks for HAK Vietnamese documents have been run yet.
- PaddleOCR source uses Apache-2.0; verify weights, dependencies, PyMuPDF and any other separately licensed components before commercial redistribution.

Official docs: https://github.com/PaddlePaddle/PaddleOCR/tree/main/docs/version3.x/pipeline_usage
