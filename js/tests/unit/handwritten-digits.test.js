'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), zlib = require('node:zlib');
const H = require('../../main/handwritten-digits.js'), weights = require('../../ocr/models/mnist-cnn.json');
const model = H.create(weights), fixture = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname, '../fixtures/handwriting/mnist-test-100.json.gz'))));
const paper = sample => ({ w: 28, h: 28, data: Uint8Array.from(Buffer.from(sample.pixels, 'base64'), x => 255 - x) });
test('handwriting CNN: JS inference matches 100 ONNX Runtime reference vectors', () => {
  let correct = 0, largestError = 0;
  for (const sample of fixture.samples) {
    const result = model.classify(Float32Array.from(Buffer.from(sample.pixels, 'base64'), x => x / 255));
    assert.equal(Number(result.text), sample.logits.indexOf(Math.max(...sample.logits)));
    sample.logits.forEach((value, i) => { largestError = Math.max(largestError, Math.abs(value - result.logits[i])); });
    if (Number(result.text) === sample.label) correct++;
  }
  assert.ok(largestError < 0.005, 'float32 numerical parity'); assert.ok(correct >= 95, 'independent handwritten test cases');
});
test('handwriting CNN: blank crop is not digit zero', () => {
  const result = model.recognize({ w: 40, h: 40, data: new Uint8Array(1600).fill(255) });
  assert.equal(result.status, 'BLANK'); assert.equal(result.text, undefined); assert.equal(result.verified, false);
});
test('handwriting CNN: separate multi-character glyphs are not interpreted as a single digit', () => {
  const data = new Uint8Array(40 * 40).fill(255);
  for (let y = 8; y < 32; y++) for (const x of [7, 8, 9, 29, 30, 31]) data[y * 40 + x] = 0;
  assert.equal(model.recognize({ w: 40, h: 40, data }).status, 'UNSUPPORTED');
});
test('handwriting CNN: invalid or oversized crop and invalid tensor are rejected', () => {
  assert.throws(() => H.normalize({ w: 4, h: 4, data: [0] }));
  assert.throws(() => H.normalize({ w: 2048, h: 1, data: new Uint8Array(2048) }));
  assert.throws(() => model.classify(new Float32Array(784).fill(NaN)));
});
test('handwriting CNN: candidates preserve original OCR text and do not approve data', () => {
  const sample = fixture.samples.find(s => s.label === 1), before = { text: '?', conf: 12 }, snapshot = JSON.stringify(before);
  const result = H.addCandidate(before, paper(sample), model);
  assert.equal(result.text, '?'); assert.equal(result.conf, 12); assert.equal(JSON.stringify(before), snapshot);
  assert.equal(result.handwriting.verified, false); assert.equal(result.handwriting.text, '1'); assert.equal(result.handwriting.offered, true);
});
test('handwriting CNN: model error remains explicit and never replaces Tesseract', () => {
  const result = H.addCandidate({ text: '0,5', conf: 80 }, {}, { recognize() { throw Error('missing model'); } });
  assert.equal(result.text, '0,5'); assert.equal(result.handwriting.status, 'UNAVAILABLE'); assert.equal(result.handwriting.offered, false);
});
test('handwriting CNN: malformed model weights fail closed', () => {
  const broken = JSON.parse(JSON.stringify(weights)); broken.weights.Parameter5.data = '';
  assert.throws(() => H.create(broken));
});

function decimal(left, right, comma = true) {
  const w = 76, h = 40, data = new Uint8Array(w * h).fill(255);
  for (const [sample, offset] of [[left, 2], [right, 44]]) {
    const pixels = Buffer.from(sample.pixels, 'base64');
    for (let y = 0; y < 28; y++) for (let x = 0; x < 28; x++) data[(y + 3) * w + x + offset] = 255 - pixels[y * 28 + x];
  }
  if (comma) for (let y = 25; y < 29; y++) for (let x = 35; x < 37; x++) data[y * w + x] = 0;
  return { w, h, data };
}
test('handwriting decimals: visible punctuation yields 0,5 and 1,5 from public handwriting, never replaces OCR', () => {
  const five = fixture.samples.find(s => s.label === 5 && model.recognize(paper(s)).status === 'CANDIDATE');
  for (const digit of [0, 1]) {
    const first = fixture.samples.find(s => s.label === digit && model.recognize(paper(s)).status === 'CANDIDATE');
    const crop = decimal(first, five), r = H.addCandidate({ text: '?', conf: 10 }, crop, model);
    assert.equal(r.text, '?'); assert.equal(r.handwriting.text, digit + ',5');
    assert.equal(r.handwriting.status, 'CANDIDATE'); assert.equal(r.handwriting.verified, false);
    assert.equal(r.handwriting.method, 'separated-number-v1');
    const already = H.addCandidate({ text: digit + '.5', conf: 90 }, crop, model);
    assert.equal(already.handwriting.offered, false);
  }
});
test('handwriting decimals: missing punctuation and extra marks are withheld', () => {
  const first = fixture.samples.find(s => s.label === 0), second = fixture.samples.find(s => s.label === 5);
  assert.equal(model.recognize(decimal(first, second, false)).status, 'UNSUPPORTED');
  const extra = decimal(first, second); for (let y = 2; y < 4; y++) extra.data[y * extra.w + 38] = 0;
  assert.equal(model.recognize(extra).status, 'UNSUPPORTED');
});
