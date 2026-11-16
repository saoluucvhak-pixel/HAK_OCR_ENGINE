/* global Buffer */
// ===== OCR LEARNING / FEATURES — đặc trưng ảnh ô (không huấn luyện AI; chỉ tính toán xác định từ điểm ảnh) =====
// Ô xám (nền sáng, nét tối) → nhị phân Otsu → hộp mực → chuẩn hóa 24×24 giữ tỉ lệ → vector:
//   [mật độ mực 12×12 (144)] + [HOG 4×4 khối × 8 hướng (128)] + [tỉ lệ khung, mật độ mực, cỡ tương đối so với ô (3)]
// Độ giống = 0,5·cos(mực) + 0,5·cos(HOG), trừ phạt khi tỉ lệ khung lệch. Cùng một hàm dùng ở renderer và main (UMD).
(function (root) {
  "use strict";
  var N = 24, PIX = 12, DIM = PIX * PIX + 128 + 3;

  function otsu(g) {
    var hist = new Uint32Array(256), n = g.length, i, sum = 0;
    for (i = 0; i < n; i++) { hist[g[i]]++; sum += g[i]; }
    var wB = 0, sB = 0, best = -1, thr = 128;
    for (var t = 0; t < 256; t++) {
      wB += hist[t]; if (!wB) continue; var wF = n - wB; if (!wF) break;
      sB += t * hist[t]; var mB = sB / wB, mF = (sum - sB) / wF, v = wB * wF * (mB - mF) * (mB - mF);
      if (v > best) { best = v; thr = t; }
    }
    return thr;
  }
  /** Hộp mực của ô xám. @returns { mask, box:{x0,y0,x1,y1}|null, ink } — chỉ coi là mực khi tối hơn ngưỡng Otsu VÀ đủ tương phản với nền */
  function inkOf(g, w, h) {
    var n = w * h, lo = 255, hi = 0, i;
    for (i = 0; i < n; i++) { if (g[i] < lo) lo = g[i]; if (g[i] > hi) hi = g[i]; }
    var mask = new Uint8Array(n);
    if (hi - lo < 40) return { mask: mask, box: null, ink: 0 }; // gần như một màu: không có nét
    var thr = otsu(g), x0 = w, y0 = h, x1 = -1, y1 = -1, ink = 0;
    for (var y = 0; y < h; y++) for (var x = 0; x < w; x++) if (g[y * w + x] <= thr) { mask[y * w + x] = 1; ink++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    return ink ? { mask: mask, box: { x0: x0, y0: y0, x1: x1 + 1, y1: y1 + 1 }, ink: ink } : { mask: mask, box: null, ink: 0 };
  }
  /** Diện tích trung bình (area-average) mask trong hộp → lưới N×N, giữ tỉ lệ (đặt giữa, đệm 2 điểm). */
  function normalize(mask, w, box) {
    var bw = box.x1 - box.x0, bh = box.y1 - box.y0, side = Math.max(bw, bh), inner = N - 4, sc = inner / side;
    var ow = Math.max(1, Math.round(bw * sc)), oh = Math.max(1, Math.round(bh * sc)), ox = Math.floor((N - ow) / 2), oy = Math.floor((N - oh) / 2);
    var out = new Float32Array(N * N);
    for (var y = 0; y < oh; y++) {
      var sy0 = box.y0 + y / sc, sy1 = box.y0 + (y + 1) / sc;
      for (var x = 0; x < ow; x++) {
        var sx0 = box.x0 + x / sc, sx1 = box.x0 + (x + 1) / sc, acc = 0, cnt = 0;
        for (var yy = Math.floor(sy0); yy < Math.min(box.y1, Math.ceil(sy1)); yy++) for (var xx = Math.floor(sx0); xx < Math.min(box.x1, Math.ceil(sx1)); xx++) { acc += mask[yy * w + xx]; cnt++; }
        out[(y + oy) * N + x + ox] = cnt ? acc / cnt : 0;
      }
    }
    return out;
  }
  function blur(a) { // làm mịn 3×3 nhẹ: ổn định trước khi lấy gradient
    var o = new Float32Array(N * N);
    for (var y = 0; y < N; y++) for (var x = 0; x < N; x++) {
      var s = 0, c = 0; for (var dy = -1; dy <= 1; dy++) for (var dx = -1; dx <= 1; dx++) { var yy = y + dy, xx = x + dx; if (yy >= 0 && yy < N && xx >= 0 && xx < N) { s += a[yy * N + xx]; c++; } }
      o[y * N + x] = s / c;
    }
    return o;
  }
  function l2(v, from, to) { var s = 0, i; for (i = from; i < to; i++) s += v[i] * v[i]; s = Math.sqrt(s) || 1; for (i = from; i < to; i++) v[i] /= s; }

  /** @param g Uint8Array xám, w, h  @param opt { cell: {w,h} kích thước ô gốc để tính cỡ tương đối }
   *  @returns { blank, vec: Float32Array(DIM), aspect, inkRatio, rel } */
  function extract(g, w, h, opt) {
    var ink = inkOf(g, w, h);
    var vec = new Float32Array(DIM);
    if (!ink.box) return { blank: true, vec: vec, aspect: 0, inkRatio: 0, rel: 0 };
    var bw = ink.box.x1 - ink.box.x0, bh = ink.box.y1 - ink.box.y0;
    var grid = normalize(ink.mask, w, ink.box), sm = blur(grid), i;
    // mật độ mực 12×12
    for (var y = 0; y < PIX; y++) for (var x = 0; x < PIX; x++) { var a = grid[(2 * y) * N + 2 * x] + grid[(2 * y) * N + 2 * x + 1] + grid[(2 * y + 1) * N + 2 * x] + grid[(2 * y + 1) * N + 2 * x + 1]; vec[y * PIX + x] = a / 4; }
    l2(vec, 0, PIX * PIX);
    // HOG: 4×4 khối 6×6, 8 hướng (không dấu), trọng số biên độ
    var base = PIX * PIX, bs = N / 4;
    for (var yy = 1; yy < N - 1; yy++) for (var xx = 1; xx < N - 1; xx++) {
      var gx = sm[yy * N + xx + 1] - sm[yy * N + xx - 1], gy = sm[(yy + 1) * N + xx] - sm[(yy - 1) * N + xx], mag = Math.sqrt(gx * gx + gy * gy);
      if (mag < 1e-6) continue;
      var ang = Math.atan2(gy, gx); if (ang < 0) ang += Math.PI; if (ang >= Math.PI) ang -= Math.PI;
      var bin = Math.min(7, Math.floor(ang / (Math.PI / 8))), by = Math.min(3, Math.floor(yy / bs)), bx = Math.min(3, Math.floor(xx / bs));
      vec[base + (by * 4 + bx) * 8 + bin] += mag;
    }
    for (i = 0; i < 16; i++) l2(vec, base + i * 8, base + i * 8 + 8);
    l2(vec, base, base + 128);
    var aspect = bw / bh, inkRatio = ink.ink / (bw * bh), rel = opt && opt.cell ? bh / Math.max(1, opt.cell.h) : 0;
    vec[base + 128] = aspect; vec[base + 129] = inkRatio; vec[base + 130] = rel;
    return { blank: false, vec: vec, aspect: aspect, inkRatio: inkRatio, rel: rel };
  }
  /** Độ giống 0…1 giữa 2 vector (cùng DIM). Ô trống chỉ giống ô trống. */
  function similarity(a, b) {
    var pb = PIX * PIX, hb = pb + 128, dp = 0, dh = 0, i;
    for (i = 0; i < pb; i++) dp += a[i] * b[i];
    for (i = pb; i < hb; i++) dh += a[i] * b[i];
    var ar = Math.min(a[hb], b[hb]) / Math.max(a[hb], b[hb], 1e-6); // 1 = cùng tỉ lệ khung
    var s = 0.5 * dp + 0.5 * dh;
    return Math.max(0, s * (0.85 + 0.15 * ar));
  }
  function toB64(vec) { var b = Buffer.from(vec.buffer, vec.byteOffset, vec.byteLength); return b.toString("base64"); }
  function fromB64(s) { var b = Buffer.from(s, "base64"), f = new Float32Array(DIM); for (var i = 0; i < DIM; i++) f[i] = b.readFloatLE(i * 4); return f; }

  var api = { DIM: DIM, extract: extract, similarity: similarity, otsu: otsu, inkOf: inkOf, toB64: toB64, fromB64: fromB64 };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else { root.HAKCore = root.HAKCore || {}; root.HAKCore.ocrFeat = api; }
})(typeof window !== "undefined" ? window : this);
