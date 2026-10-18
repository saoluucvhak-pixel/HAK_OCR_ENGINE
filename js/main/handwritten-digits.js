'use strict';
// Fixed pretrained MNIST CNN from ONNX model zoo. CPU inference, no network or native runtime.
function weights(model) {
  const sizes = { Parameter5: 200, Parameter6: 8, Parameter87: 3200, Parameter88: 16, Parameter193: 2560, Parameter194: 10 };
  const out = {};
  for (const [name, length] of Object.entries(sizes)) {
    const bytes = Buffer.from(model.weights[name].data, 'base64');
    if (bytes.length !== length * 4) throw Error('Invalid handwriting model weights: ' + name);
    const a = new Float32Array(length);
    for (let i = 0; i < length; i++) { a[i] = bytes.readFloatLE(i * 4); if (!Number.isFinite(a[i])) throw Error('Non-finite handwriting weight'); }
    out[name] = a;
  }
  return out;
}
function convolution(input, channels, height, width, kernels, biases, outputChannels) {
  const out = new Float32Array(outputChannels * height * width), plane = height * width;
  for (let oc = 0; oc < outputChannels; oc++) for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    let sum = 0;
    for (let ic = 0; ic < channels; ic++) for (let ky = 0; ky < 5; ky++) {
      const iy = y + ky - 2; if (iy < 0 || iy >= height) continue;
      for (let kx = 0; kx < 5; kx++) {
        const ix = x + kx - 2; if (ix >= 0 && ix < width) sum += input[ic * plane + iy * width + ix] * kernels[((oc * channels + ic) * 5 + ky) * 5 + kx];
      }
    }
    // ONNX Conv, Add and Relu each have float32 output.
    out[oc * plane + y * width + x] = Math.max(0, Math.fround(Math.fround(sum) + biases[oc]));
  }
  return out;
}
function pool(input, channels, height, width, stride) {
  const h = Math.floor(height / stride), w = Math.floor(width / stride), out = new Float32Array(channels * h * w);
  for (let c = 0; c < channels; c++) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let max = -Infinity;
    for (let j = 0; j < stride; j++) for (let i = 0; i < stride; i++) max = Math.max(max, input[(c * height + y * stride + j) * width + x * stride + i]);
    out[(c * h + y) * w + x] = max;
  }
  return out;
}
function normalize(item) {
  const { w, h, data } = item || {};
  if (!Number.isInteger(w) || !Number.isInteger(h) || w < 1 || h < 1 || w > 1024 || h > 1024 || !data || data.length !== w * h) throw Error('Invalid handwriting crop');
  let x0 = w, y0 = h, x1 = -1, y1 = -1, ink = 0;
  const columns = new Uint32Array(w);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (data[y * w + x] < 180) {
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); columns[x]++; ink++;
  }
  if (ink < 6 || x1 < x0) return { status: 'BLANK' };
  const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
  if (bh < 6 || bw > bh * 1.5) return { status: 'UNSUPPORTED', reason: 'single digit only' };
  let gap = 0;
  for (let x = x0; x <= x1; x++) {
    if (!columns[x]) gap++; else { if (gap > Math.max(2, bh * 0.15)) return { status: 'UNSUPPORTED', reason: 'multiple separated glyphs' }; gap = 0; }
  }
  const scale = 20 / Math.max(bw, bh), tw = Math.max(1, Math.round(bw * scale)), th = Math.max(1, Math.round(bh * scale));
  const resized = new Float32Array(tw * th);
  let mass = 0, mx = 0, my = 0;
  for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) {
    const sx = Math.max(0, Math.min(bw - 1, (x + 0.5) * bw / tw - 0.5)), sy = Math.max(0, Math.min(bh - 1, (y + 0.5) * bh / th - 0.5));
    const xa = Math.floor(sx), ya = Math.floor(sy), xb = Math.min(bw - 1, xa + 1), yb = Math.min(bh - 1, ya + 1), dx = sx - xa, dy = sy - ya;
    const pixel = (xx, yy) => (255 - data[(y0 + yy) * w + x0 + xx]) / 255;
    const value = pixel(xa, ya) * (1 - dx) * (1 - dy) + pixel(xb, ya) * dx * (1 - dy) + pixel(xa, yb) * (1 - dx) * dy + pixel(xb, yb) * dx * dy;
    resized[y * tw + x] = value; mass += value; mx += x * value; my += y * value;
  }
  if (!mass) return { status: 'BLANK' };
  const tensor = new Float32Array(784), ox = Math.round(13.5 - mx / mass), oy = Math.round(13.5 - my / mass);
  for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) if (x + ox >= 0 && x + ox < 28 && y + oy >= 0 && y + oy < 28) tensor[(y + oy) * 28 + x + ox] = resized[y * tw + x];
  return { status: 'READY', tensor };
}
function create(model) {
  if (!model || model.id !== 'hak-mnist-cnn-onnx12-v1') throw Error('Unsupported handwriting model');
  const W = weights(model);
  function classify(tensor) {
    if (!tensor || tensor.length !== 784 || Array.from(tensor).some(x => !Number.isFinite(x) || x < 0 || x > 1)) throw Error('Expected normalized 28x28 tensor');
    const a = pool(convolution(tensor, 1, 28, 28, W.Parameter5, W.Parameter6, 8), 8, 28, 28, 2);
    const b = pool(convolution(a, 8, 14, 14, W.Parameter87, W.Parameter88, 16), 16, 14, 14, 3);
    const logits = Array.from({ length: 10 }, (_, c) => {
      let sum = 0; for (let i = 0; i < 256; i++) sum += b[i] * W.Parameter193[i * 10 + c];
      return Math.fround(Math.fround(sum) + W.Parameter194[c]);
    });
    const max = Math.max(...logits), exp = logits.map(x => Math.exp(x - max)), total = exp.reduce((a, b) => a + b, 0);
    const candidates = exp.map((value, digit) => ({ text: String(digit), score: value / total })).sort((a, b) => b.score - a.score);
    return { text: candidates[0].text, score: candidates[0].score, margin: candidates[0].score - candidates[1].score, candidates: candidates.slice(0, 3), logits, model: model.id, verified: false };
  }
  function recognize(item) {
    const sequence = segmentNumber(item);
    if (sequence && sequence.status === 'READY') {
      const parts = sequence.parts.map(part => part.separator ? { text: ',', score: 1, margin: 1 } : recognize(part.crop));
      const confident = parts.every(part => part.status === 'CANDIDATE' || part.text === ',');
      return { status: confident ? 'CANDIDATE' : 'NEEDS_REVIEW', text: parts.map(part => part.text || '?').join(''),
        score: Math.min(...parts.map(part => part.score || 0)), margin: Math.min(...parts.map(part => part.margin || 0)),
        model: model.id, method: 'separated-number-v1', verified: false,
        warning: 'Gợi ý ghép chữ số tách rời và dấu thập phân; phải đối chiếu ảnh gốc, không tự ghi dữ liệu.' };
    }
    if (sequence && sequence.status === 'UNSUPPORTED') return { status: 'UNSUPPORTED', reason: sequence.reason, model: model.id, verified: false };
    const prepared = normalize(item);
    if (prepared.status !== 'READY') return { status: prepared.status, reason: prepared.reason, model: model.id, verified: false };
    const result = classify(prepared.tensor);
    delete result.logits;
    result.status = result.score >= 0.95 && result.margin >= 0.8 ? 'CANDIDATE' : 'NEEDS_REVIEW';
    // A softmax score is not calibrated field accuracy or approval.
    result.warning = 'Chỉ gợi ý một chữ số 0–9; cần người dùng đối chiếu ảnh gốc.';
    return result;
  }
  return { classify, recognize, model: model.id };
}
// Conservative column segmentation: never invent a missing separator or split touching ink.
function segmentNumber(item) {
  const { w, h, data } = item || {};
  if (!Number.isInteger(w) || !Number.isInteger(h) || w < 1 || h < 1 || w > 1024 || h > 1024 || !data || data.length !== w * h) return null;
  const runs = []; let run;
  for (let x = 0; x < w; x++) {
    let top = h, bottom = -1;
    for (let y = 0; y < h; y++) if (data[y * w + x] < 180) { top = Math.min(top, y); bottom = y; }
    if (bottom >= 0) {
      if (!run) { run = { x0: x, x1: x, y0: top, y1: bottom }; runs.push(run); }
      run.x1 = x; run.y0 = Math.min(run.y0, top); run.y1 = Math.max(run.y1, bottom);
    } else run = null;
  }
  if (runs.length < 2) return null;
  const reject = reason => ({ status: 'UNSUPPORTED', reason });
  const height = Math.max(...runs.map(r => r.y1 - r.y0 + 1));
  if (height < 8 || runs.length > 5) return reject('ambiguous number segmentation');
  const baseline = Math.max(...runs.filter(r => r.y1 - r.y0 + 1 >= height * 0.65).map(r => r.y1));
  let separators = 0, digits = 0;
  const parts = [];
  for (let i = 0; i < runs.length; i++) {
    const r = runs[i], rw = r.x1 - r.x0 + 1, rh = r.y1 - r.y0 + 1;
    if (i && r.x0 - runs[i - 1].x1 > height * 0.9) return reject('glyph spacing too wide');
    if (rh <= height * 0.35 && rw <= height * 0.3 && r.y0 >= baseline - height * 0.3) {
      if (i === 0 || i === runs.length - 1 || ++separators > 1) return reject('ambiguous decimal separator');
      parts.push({ separator: true }); continue;
    }
    if (rh < height * 0.65 || rw > height * 1.2) return reject('noise or unsupported symbol');
    digits++;
    const crop = { w: rw + 8, h: rh + 8, data: new Uint8Array((rw + 8) * (rh + 8)).fill(255) };
    for (let y = 0; y < rh; y++) for (let x = 0; x < rw; x++) crop.data[(y + 4) * crop.w + x + 4] = data[(r.y0 + y) * w + r.x0 + x];
    parts.push({ crop });
  }
  // Require visible punctuation for decimal proposals; integer strings are retained for manual review.
  if (separators !== 1 || digits < 2 || digits > 4) return reject('separated decimal with visible separator required');
  return { status: 'READY', parts };
}
function addCandidate(reading, item, recognizer) {
  let result;
  try { result = recognizer.recognize(item); }
  catch (error) { result = { status: 'UNAVAILABLE', verified: false, error: String(error.message || error) }; }
  const raw = String(reading.text || '').trim(), numeric = /^\d+(?:[.,]\d+)?$/.test(raw) ? Number(raw.replace(',', '.')) : NaN;
  result.offered = result.status === 'CANDIDATE' && Number(String(result.text).replace(',', '.')) !== numeric;
  // Preserve Tesseract's original text/confidence; the consumer must request a human decision.
  return Object.assign({}, reading, { handwriting: result });
}
module.exports = { create, normalize, addCandidate, segmentNumber };
