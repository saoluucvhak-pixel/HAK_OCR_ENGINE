"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), zlib = require("node:zlib");
const P = require("../../main/paddle-rec.js");
const FX = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname, "../fixtures/paddle/parity.json.gz"))));
const bytes = (s) => new Uint8Array(Buffer.from(s, "base64"));

test("đổi cỡ ảnh khớp cv2.INTER_LINEAR (phóng / thu / ảnh 1 điểm): lệch tối đa 1 mức xám, gần như mọi điểm trùng", () => {
  for (const c of FX.resize) {
    const js = P.resizeLinear(bytes(c.src), c.w, c.h, c.dw, c.dh), cv = bytes(c.cv2), name = c.w + "×" + c.h + "→" + c.dw + "×" + c.dh;
    let max = 0, diff = 0; for (let i = 0; i < cv.length; i++) { const d = Math.abs(js[i] - cv[i]); max = Math.max(max, d); if (d) diff++; }
    assert.ok(max <= 1, name + " lệch " + max);
    // ảnh nguồn cao 1 điểm phóng 48 lần: OpenCV đi nhánh ngang khác (lệch ±1 ở ~14% điểm) — không xảy ra với ô thật (cao ≥ 20 điểm)
    if (c.h > 1) assert.ok(diff / cv.length <= 0.01, name + " tỷ lệ điểm lệch " + diff / cv.length);
  }
});

test("tiền xử lý khớp PaddleX OCRReisizeNormImg: cùng kích thước tensor, giá trị lệch ≤ 1/127,5", () => {
  for (const c of FX.preprocess) {
    const p = P.preprocess({ data: bytes(c.data), w: c.w, h: c.h }), ref = bytes(c.ch0), W = p.dims[3];
    assert.deepEqual(p.dims, [1].concat(c.dims), c.id);
    for (let i = 0; i < 48 * W; i++) assert.ok(Math.abs(Math.round(p.data[i] * 127.5 + 127.5) - ref[i]) <= 1, c.id + " điểm " + i);
    assert.deepEqual(Array.from(p.data.subarray(48 * W, 2 * 48 * W)), Array.from(p.data.subarray(0, 48 * W)));   // 3 kênh như nhau
  }
  assert.throws(() => P.preprocess({ data: new Uint8Array(3), w: 4, h: 4 }), /không hợp lệ/);
});

test("giải mã CTC: bỏ blank và ký tự trùng liền kề, giữ ký tự lặp cách nhau bởi blank; điểm = trung bình", () => {
  const chars = P.charsetOf(["1", "0", "a"]);            // blank, 1, 0, a, " "
  assert.deepEqual(chars, ["blank", "1", "0", "a", " "]);
  const steps = [[0, 0.9], [1, 0.8], [1, 0.6], [0, 0.9], [1, 0.7], [2, 1.0], [4, 0.5], [3, 0.9]];   // [lớp thắng, xác suất]
  const C = chars.length, probs = new Float32Array(steps.length * C);
  steps.forEach(([k, p], t) => { for (let c = 0; c < C; c++) probs[t * C + c] = c === k ? p : (1 - p) / (C - 1); });
  const r = P.ctcDecode(probs, steps.length, C, chars);
  assert.equal(r.text, "110 a");
  assert.ok(Math.abs(r.score - (0.8 + 0.7 + 1.0 + 0.5 + 0.9) / 5) < 1e-6);
  assert.deepEqual(P.ctcDecode(new Float32Array([1, 0, 0, 0, 0]), 1, C, chars), { text: "", score: 0 });   // toàn blank: chuỗi rỗng, không phải "0"
});

test("bộ nhận dạng chạy với onnxruntime bất kỳ (giả lập): đúng tên đầu vào, đổi điểm sang thang 0–100, từ chối model lệch bộ ký tự", async () => {
  const seen = [];
  const fakeOrt = (classes) => ({
    Tensor: function (type, data, dims) { this.type = type; this.data = data; this.dims = dims; },
    InferenceSession: { create: async () => ({ inputNames: ["x"], outputNames: ["y"], release: async () => {},
      run: async (feeds) => { seen.push(feeds.x.dims); const T = 2, d = new Float32Array(T * classes); d[1] = 0.9; d[classes + 0] = 1; return { y: { dims: [1, T, classes], data: d } }; } }) }
  });
  const r = await P.createPaddleRecognizer({ model: "m.onnx", dict: ["7", "x"], ort: fakeOrt(4) });
  assert.deepEqual(await r.batch([{ data: new Uint8Array(30 * 20).fill(255), w: 30, h: 20 }]), [{ text: "7", conf: 90 }]);
  assert.deepEqual(seen[0], [1, 3, 48, 320]);
  const bad = await P.createPaddleRecognizer({ model: "m.onnx", dict: ["7"], ort: fakeOrt(4) });
  await assert.rejects(bad.recognize({ data: new Uint8Array(4).fill(0), w: 2, h: 2 }), /không khớp/);
});

// Chạy thật trên model ONNX khi có: HAK_PADDLE_MODEL_DIR chứa inference.onnx + dict.json (xuất bằng js/scripts/paddle/convert.sh).
const DIR = process.env.HAK_PADDLE_MODEL_DIR;
let ort = null; try { if (DIR) ort = require("onnxruntime-node"); } catch (e) { ort = null; }
test("ONNX trong Node khớp PaddleOCR Python (paddle_static) trên ô thật của app", { skip: !(DIR && ort) && "cần HAK_PADDLE_MODEL_DIR + onnxruntime-node" }, async () => {
  const rec = await P.createPaddleRecognizer({ model: path.join(DIR, "inference.onnx"), dict: JSON.parse(fs.readFileSync(path.join(DIR, "dict.json"), "utf8")), ort });
  let same = 0, maxD = 0;
  for (const c of FX.recognize) { const r = await rec.recognize({ data: bytes(c.data), w: c.w, h: c.h }); if (r.text === c.text) same++; maxD = Math.max(maxD, Math.abs(r.score - c.score)); }
  await rec.release();
  assert.ok(same >= FX.recognize.length - 1, "khớp " + same + "/" + FX.recognize.length);
  assert.ok(maxD < 0.02, "lệch điểm " + maxD);
});
