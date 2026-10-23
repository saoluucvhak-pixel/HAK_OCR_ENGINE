// ===== MAIN / PADDLE-REC — nhận dạng dòng chữ PaddleOCR (PP-OCRv5 rec, CTC) bằng onnxruntime-node, OFFLINE, không cần Python =====
// - Model ONNX xuất bằng js/scripts/paddle/convert.sh (paddle2onnx, chạy trên Linux/WSL); bộ ký tự lấy từ inference.yml của model.
// - Tiền xử lý bám đúng PaddleX OCRReisizeNormImg: giữ tỷ lệ, cao 48, rộng ≥ 320 (tối đa 3200), (x/255 − 0,5)/0,5, đệm 0.
// - Giải mã bám đúng CTCLabelDecode: argmax từng bước, bỏ bước trùng liền kề và blank (0); điểm = trung bình xác suất ký tự giữ lại.
// - Chỉ là ĐỀ XUẤT đọc chữ: không tự duyệt, không thay kết quả Tesseract; host quyết định đối chiếu / đánh dấu cần kiểm tra.
"use strict";
const { unpacked } = require("./ocr-service.js");

const IMG_H = 48, MIN_W = 320, MAX_W = 3200;

/**
 * Đổi cỡ song tuyến GIỐNG HỆT cv2.resize(INTER_LINEAR) cho ảnh uint8: tâm điểm ảnh lệch 0,5, kẹp biên, hệ số số nguyên cố định
 * (× 2048, làm tròn), lượt ngang giữ số nguyên, lượt dọc ((b0·(S0>>4))>>16 + (b1·(S1>>4))>>16 + 2)>>2 như nhánh SIMD của OpenCV.
 */
const COEF = 2048;
function coefs(n, dn) {
  const scale = n / dn, idx = new Int32Array(dn), c0 = new Int32Array(dn), c1 = new Int32Array(dn);
  for (let d = 0; d < dn; d++) {
    let f = Math.fround((d + 0.5) * scale - 0.5), s = Math.floor(f); f = Math.fround(f - s);
    if (s < 0) { s = 0; f = 0; } if (s >= n - 1) { s = n - 1; f = 0; }
    idx[d] = s; c0[d] = Math.round(Math.fround(1 - f) * COEF); c1[d] = Math.round(f * COEF);
  }
  return { idx, c0, c1 };
}
function resizeLinear(src, w, h, dw, dh) {
  if (dw === w && dh === h) return Uint8Array.from(src.subarray ? src.subarray(0, w * h) : src.slice(0, w * h));
  const X = coefs(w, dw), Y = coefs(h, dh), out = new Uint8Array(dw * dh), rows = new Map();
  const hrow = (y) => {                                   // lượt ngang: số nguyên S·a0 + S'·a1 (≤ 255·2048)
    let r = rows.get(y); if (r) return r;
    r = new Int32Array(dw); const o = y * w;
    for (let x = 0; x < dw; x++) { const s = X.idx[x], s1 = Math.min(w - 1, s + 1); r[x] = src[o + s] * X.c0[x] + src[o + s1] * X.c1[x]; }
    rows.set(y, r); if (rows.size > 4) rows.delete(rows.keys().next().value);
    return r;
  };
  for (let y = 0; y < dh; y++) {
    const s = Y.idx[y], r0 = hrow(s), r1 = hrow(Math.min(h - 1, s + 1)), b0 = Y.c0[y], b1 = Y.c1[y], o = y * dw;
    for (let x = 0; x < dw; x++) {
      const v = (((b0 * (r0[x] >> 4)) >> 16) + ((b1 * (r1[x] >> 4)) >> 16) + 2) >> 2;
      out[o + x] = v < 0 ? 0 : v > 255 ? 255 : v;
    }
  }
  return out;
}

/** Ảnh xám { data|g, w, h } → { data: Float32Array [3 × 48 × W], dims: [1, 3, 48, W], resized: bề rộng phần ảnh thật } */
function preprocess(img) {
  const g = img.data || img.g, w = img.w, h = img.h;
  if (!g || !(w > 0) || !(h > 0) || g.length < w * h) throw Error("Ảnh ô không hợp lệ");
  const ratio = w / h, imgW = Math.min(MAX_W, Math.trunc(IMG_H * Math.max(MIN_W / IMG_H, ratio)));
  const rw = Math.min(imgW, Math.ceil(IMG_H * ratio));
  const r = resizeLinear(g, w, h, rw, IMG_H), plane = IMG_H * imgW, data = new Float32Array(3 * plane);   // phần đệm = 0
  for (let y = 0; y < IMG_H; y++) for (let x = 0; x < rw; x++) {
    const v = (r[y * rw + x] / 255 - 0.5) / 0.5, p = y * imgW + x;
    data[p] = v; data[plane + p] = v; data[2 * plane + p] = v;   // xám → 3 kênh như nhau (BGR)
  }
  return { data, dims: [1, 3, IMG_H, imgW], resized: rw };
}

/** probs [T × C] (đã softmax) → { text, score } theo CTCLabelDecode; chars[0] là blank. */
function ctcDecode(probs, T, C, chars) {
  let text = "", sum = 0, n = 0, prev = -1;
  for (let t = 0; t < T; t++) {
    let best = 0, bp = probs[t * C];
    for (let c = 1; c < C; c++) { const p = probs[t * C + c]; if (p > bp) { bp = p; best = c; } }
    if (best !== 0 && best !== prev) { text += chars[best]; sum += bp; n++; }
    prev = best;
  }
  return { text, score: n ? sum / n : 0 };
}

/** Bộ ký tự đầy đủ của đầu ra: blank + character_dict + dấu cách (use_space_char mặc định của PaddleX). */
function charsetOf(dict, useSpace) { return ["blank"].concat(dict, useSpace === false ? [] : [" "]); }

/**
 * opts.model: đường dẫn inference.onnx; opts.dict: mảng ký tự (character_dict); opts.ort: thư viện (mặc định require("onnxruntime-node"))
 * Trả Promise<{ recognize(img) → { text, score }, batch(items) → [{ text, conf (0–100) }], release() }>
 */
async function createPaddleRecognizer(opts) {
  opts = opts || {};
  const ort = opts.ort || require("onnxruntime-node");
  const session = await ort.InferenceSession.create(unpacked(opts.model), { intraOpNumThreads: opts.threads || 0, graphOptimizationLevel: "all" });
  const chars = charsetOf(opts.dict || [], opts.useSpace), inName = session.inputNames[0], outName = session.outputNames[0];
  async function recognize(img) {
    const p = preprocess(img), out = (await session.run({ [inName]: new ort.Tensor("float32", p.data, p.dims) }))[outName], T = out.dims[1], C = out.dims[2];
    if (C !== chars.length) throw Error("Model có " + C + " lớp đầu ra nhưng bộ ký tự có " + chars.length + " — model và bộ ký tự không khớp");
    return ctcDecode(out.data, T, C, chars);
  }
  return {
    chars, recognize,
    async batch(items) { const out = []; for (const it of items) { const r = await recognize(it); out.push({ text: r.text, conf: Math.round(r.score * 1000) / 10 }); } return out; },
    release: () => session.release()
  };
}

module.exports = { createPaddleRecognizer, preprocess, resizeLinear, ctcDecode, charsetOf };
