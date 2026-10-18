# Shared attendance validation for Electron

This branch adds `js/core/ocr-learning/attendance-validation.js` as a directly reusable, dependency-free Node/browser module, alongside the existing source ZIP. The ZIP at main commit `1a1e627edf0392197f7f010b54b77feb15d3aadf` was inspected; its JavaScript OCR modules are identical to those already in the payroll app.

The new module is a validation upgrade, not a new handwriting recognition model. It preserves blank versus zero, rejects invalid calendar/day layouts, flags both duplicated employee rows, rejects ambiguous numeric text and negative hours, and exposes a read-only numeric/blank/invalid summary. `payrollReady` is always false. Existing callers still own the human review and repository write path.

Node: `const validation = require('./js/core/ocr-learning/attendance-validation.js')`.
Browser: load the script before the payroll UI; it provides `HAKCore.ocrRules`.

Run `node --test js/tests/unit/attendance-validation.test.js`.

Consumer integration pins a source commit, records a SHA256 checksum, and checks parity in CI. It copies this file to `LuongHAK_Offline/core/ocr-learning/rules.js`, preserving the existing browser API. No Python executable, model download, network OCR call or real document is introduced.
