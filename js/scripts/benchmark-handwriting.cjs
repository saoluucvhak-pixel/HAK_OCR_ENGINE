'use strict';
const fs = require('node:fs'), path = require('node:path'), zlib = require('node:zlib');
const { create, normalize } = require('../main/handwritten-digits.js');
const model = create(require('../ocr/models/mnist-cnn.json'));
const reference = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname, '../tests/fixtures/handwriting/mnist-test-100.json.gz'))));
let maxError = 0, referenceMatches = 0;
for (const sample of reference.samples) {
  const pixels = Buffer.from(sample.pixels, 'base64');
  const result = model.classify(Float32Array.from(pixels, x => x / 255));
  if (result.text === String(sample.logits.indexOf(Math.max(...sample.logits)))) referenceMatches++;
  sample.logits.forEach((value, i) => { maxError = Math.max(maxError, Math.abs(value - result.logits[i])); });
}
console.log(JSON.stringify({ referenceMatches, referenceCases: reference.samples.length, maxLogitError: maxError }));
if (referenceMatches !== reference.samples.length || maxError > 0.005) throw Error('JS inference differs from ONNX Runtime reference');
const data = fs.readFileSync(path.resolve(process.argv[2])), count = data.readUInt32LE(0), started = Date.now();
const report = { model: model.model, dataset: 'MNIST official test split; handwritten digits, not company timesheets', count, referenceMatches, maxLogitError: maxError, correct: 0, normalizedCorrect: 0, supported: 0, suggested: 0, wrongSuggestions: 0, confusion: Array.from({ length: 10 }, () => Array(10).fill(0)) };
for (let i = 0; i < count; i++) {
  const offset = 4 + i * 785, label = data[offset], pixels = data.subarray(offset + 1, offset + 785);
  const result = model.classify(Float32Array.from(pixels, x => x / 255));
  report.confusion[label][Number(result.text)]++; if (result.text === String(label)) report.correct++;
  const normalized = normalize({ w: 28, h: 28, data: Uint8Array.from(pixels, x => 255 - x) });
  if (normalized.status === 'READY') {
    report.supported++; const candidate = model.classify(normalized.tensor);
    if (candidate.text === String(label)) report.normalizedCorrect++;
    if (candidate.score >= 0.95 && candidate.margin >= 0.8) { report.suggested++; if (candidate.text !== String(label)) report.wrongSuggestions++; }
  }
  if ((i + 1) % 1000 === 0) console.log((i + 1) + '/' + count);
}
report.accuracy = report.correct / count; report.normalizedAccuracy = report.normalizedCorrect / count; report.elapsedMs = Date.now() - started;
fs.writeFileSync(path.resolve(process.argv[3] || 'handwriting-benchmark-results.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
