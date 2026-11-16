// ===== CORE / OCR-LEARNING / LAYOUT — chữ ký bố cục bảng (OCR_LAYOUT_LIBRARY) =====
// Chữ ký = vị trí cột/dòng CHUẨN HÓA theo khung bảng (0..1) → không phụ thuộc độ phân giải / vị trí bảng trên trang (căn chỉnh hình học).
// KHÔNG đọc ô bằng toạ độ cũ: bảng luôn được dựng lại từ ảnh; thư viện chỉ cho biết "bố cục này đã từng gặp" hay "lệch bố cục đã lưu".
(function (root) {
  "use strict";
  function cluster(vals, tol) {
    var v = vals.slice().sort(function (a, b) { return a - b; }), out = [], cur = [];
    v.forEach(function (x) { if (cur.length && x - cur[cur.length - 1] > tol) { out.push(cur); cur = []; } cur.push(x); });
    if (cur.length) out.push(cur);
    return out.map(function (g) { return g.reduce(function (s, x) { return s + x; }, 0) / g.length; });
  }
  /** res: kết quả analyze { cells:[{cx,cy,...}], box:{x0,y0,x1,y1}, w, h } → { cols[], rows[], nCols, nRows, aspect } hoặc null */
  function signature(res) {
    if (!res || !res.cells || res.cells.length < 4) return null;
    var xs = res.cells.map(function (c) { return c.x0; }).concat(res.cells.map(function (c) { return c.x1; })), ys = res.cells.map(function (c) { return c.y0; }).concat(res.cells.map(function (c) { return c.y1; }));
    var b = res.box && res.box.x1 > res.box.x0 ? res.box : { x0: Math.min.apply(null, xs), x1: Math.max.apply(null, xs), y0: Math.min.apply(null, ys), y1: Math.max.apply(null, ys) };
    var bw = b.x1 - b.x0, bh = b.y1 - b.y0; if (bw < 10 || bh < 10) return null;
    var cols = cluster(res.cells.map(function (c) { return (c.cx - b.x0) / bw; }), 0.008), rows = cluster(res.cells.map(function (c) { return (c.cy - b.y0) / bh; }), 0.004);
    return { cols: cols.map(r4), rows: rows.map(r4), nCols: cols.length, nRows: rows.length, aspect: r4(bw / bh) };
  }
  function r4(x) { return Math.round(x * 10000) / 10000; }
  function meanNearest(a, b) { if (!a.length || !b.length) return 1; var s = 0; a.forEach(function (x) { var d = 1; b.forEach(function (y) { var e = Math.abs(x - y); if (e < d) d = e; }); s += d; }); return s / a.length; }
  /** 0..1 — cột phải khớp chặt (số cột + vị trí); số dòng được phép khác (mỗi tháng/phòng ban số người khác nhau). */
  function similarity(a, b) {
    if (!a || !b) return 0;
    var cc = Math.min(a.nCols, b.nCols) / Math.max(a.nCols, b.nCols), cd = (meanNearest(a.cols, b.cols) + meanNearest(b.cols, a.cols)) / 2, colScore = Math.max(0, 1 - cd / 0.015) * cc * cc;
    var sp = function (r) { return r.length > 1 ? (r[r.length - 1] - r[0]) / (r.length - 1) : 0; }, sa = sp(a.rows), sb = sp(b.rows), rowScore = sa && sb ? Math.min(sa, sb) / Math.max(sa, sb) : 0.5;
    var asp = Math.min(a.aspect, b.aspect) / Math.max(a.aspect, b.aspect);
    return 0.65 * colScore + 0.2 * rowScore + 0.15 * asp;
  }
  /** layouts: [{id,name,sig}] → { status: NEW (thư viện chưa có bố cục) | MATCH | MISMATCH, id, score, name } */
  function match(sig, layouts, th) {
    th = th || 0.9; if (!sig) return { status: "MISMATCH", id: "", score: 0, reason: "không dựng được khung bảng" };
    if (!layouts || !layouts.length) return { status: "NEW", id: "", score: 0 };
    var best = null; layouts.forEach(function (l) { var s = similarity(sig, l.sig); if (!best || s > best.score) best = { id: l.id, name: l.name, score: s }; });
    return best.score >= th ? { status: "MATCH", id: best.id, name: best.name, score: best.score } : { status: "MISMATCH", id: best.id, name: best.name, score: best.score, reason: "lệch so với bố cục gần nhất (" + best.name + ", độ khớp " + Math.round(best.score * 100) + "%)" };
  }
  var API = { signature: signature, similarity: similarity, match: match };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else { root.HAKCore = root.HAKCore || {}; root.HAKCore.ocrLayout = API; }
})(typeof self !== "undefined" ? self : this);
