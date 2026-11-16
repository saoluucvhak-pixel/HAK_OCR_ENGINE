// ===== CORE / OCR-LEARNING / PDF-TEXT — dùng LỚP CHỮ của PDF trước khi OCR (V7 GĐ6) =====
// PDF xuất từ Excel/Word có lớp chữ: chữ và số chính xác tuyệt đối, không cần nhận dạng ảnh. PDF scan không có lớp chữ → trả null → OCR như cũ.
// items: kết quả pdf.js getTextContent().items đã đổi sang toạ độ ảnh trang: [{ str, x0, y0, x1, y1 }].
(function (root) {
  "use strict";
  var TP = typeof module !== "undefined" && module.exports ? require("../timesheet-parse.js") : root.HAKCore && root.HAKCore.tsparse;
  var G = typeof module !== "undefined" && module.exports ? require("../table-grid.js") : root.HAKCore && root.HAKCore.grid;
  function median(a) { var s = a.slice().sort(function (x, y) { return x - y; }); return s[Math.floor(s.length / 2)] || 0; }
  /** Đổi 1 item pdf.js (transform, width, height) sang hình chữ nhật trên ảnh trang theo viewport.transform */
  function toRect(it, vt) {
    var e = it.transform[4], f = it.transform[5], ap = function (x, y) { return [vt[0] * x + vt[2] * y + vt[4], vt[1] * x + vt[3] * y + vt[5]]; };
    var p = ap(e, f), q = ap(e + it.width, f + (it.height || Math.abs(it.transform[3]) || 0));
    return { str: it.str, x0: Math.min(p[0], q[0]), x1: Math.max(p[0], q[0]), y0: Math.min(p[1], q[1]), y1: Math.max(p[1], q[1]) };
  }
  /** Gộp các mảnh chữ cùng dòng, sát nhau thành 1 ô (ví dụ "0" "," "5" → "0,5"); mảnh cách xa vẫn là các ô riêng. */
  function mergeRuns(items) {
    var it = items.filter(function (x) { return String(x.str).trim(); }).map(function (x) { return Object.assign({}, x, { str: String(x.str).trim() }); });
    it.sort(function (a, b) { return (a.y0 + a.y1) / 2 - (b.y0 + b.y1) / 2 || a.x0 - b.x0; });
    var out = [];
    it.forEach(function (x) {
      var h = x.y1 - x.y0, last = out[out.length - 1];
      if (last && Math.abs((last.y0 + last.y1) / 2 - (x.y0 + x.y1) / 2) < h * 0.5 && x.x0 - last.x1 < h * 0.25 && x.x0 - last.x1 > -h * 0.5 && /^[0-9.,]+$/.test(last.str + x.str)) { last.str += x.str; last.x1 = Math.max(last.x1, x.x1); last.y0 = Math.min(last.y0, x.y0); last.y1 = Math.max(last.y1, x.y1); }
      else out.push(Object.assign({}, x));
    });
    return out;
  }
  /** Chữ trong PDF không có đường kẻ: kéo mỗi ô ra đủ dải dòng × dải cột của nó (để bộ dựng bảng nối được ô kề nhau như bảng có đường kẻ). */
  function snapToGrid(cells) {
    var hs = cells.map(function (c) { return c.y1 - c.y0; }), th = median(hs) * 0.6 || 6;
    var byY = cells.slice().sort(function (a, b) { return a.cy - b.cy; }), rows = [];
    byY.forEach(function (c) { var r = rows[rows.length - 1]; if (r && Math.abs(c.cy - r.cy) <= th) { r.cells.push(c); r.cy = r.cells.reduce(function (s, x) { return s + x.cy; }, 0) / r.cells.length; } else rows.push({ cy: c.cy, cells: [c] }); });
    // dòng ít ô (tiêu đề, ghi chú) không thuộc bảng: tách ra, không dùng để chia cột
    var tableRows = rows.filter(function (r) { return r.cells.length >= 4; }), loose = [];
    rows.forEach(function (r) { if (r.cells.length < 4) r.cells.forEach(function (c) { loose.push(c); }); });
    tableRows.forEach(function (r, i) { var up = i ? (tableRows[i - 1].cy + r.cy) / 2 : r.cy - (tableRows[1] ? (tableRows[1].cy - r.cy) / 2 : 10), dn = i < tableRows.length - 1 ? (tableRows[i + 1].cy + r.cy) / 2 : r.cy + (i ? (r.cy - tableRows[i - 1].cy) / 2 : 10); r.cells.forEach(function (c) { c.y0 = up; c.y1 = dn; }); });
    var tc = []; tableRows.forEach(function (r) { r.cells.forEach(function (c) { tc.push(c); }); });
    var byX = tc.slice().sort(function (a, b) { return a.bb.x0 - b.bb.x0; }), cols = [];
    byX.forEach(function (c) { var k = cols[cols.length - 1]; if (k && c.bb.x0 <= k.x1) { k.cells.push(c); k.x1 = Math.max(k.x1, c.bb.x1); } else cols.push({ x0: c.bb.x0, x1: c.bb.x1, cells: [c] }); });
    cols.forEach(function (k, i) { var l = i ? (cols[i - 1].x1 + k.x0) / 2 : k.x0 - 5, r = i < cols.length - 1 ? (k.x1 + cols[i + 1].x0) / 2 : k.x1 + 5; k.cells.forEach(function (c) { c.x0 = l; c.x1 = r; c.cx = (l + r) / 2; }); });
    tc.forEach(function (c) { c.cy = (c.y0 + c.y1) / 2; });
    return { table: tc, loose: loose };
  }
  /** → { usable, reason, cells, table, title, period, nNum } ; usable=false nếu không phải bảng chấm công dạng chữ (ít chữ, không dựng được bảng) */
  function analyze(items, page, opt) {
    opt = opt || {}; var runs = mergeRuns(items || []);
    var nNum = runs.filter(function (r) { return /^[0-9]+([.,][0-9]+)?$/.test(r.str); }).length;
    if (runs.length < (opt.minItems || 30) || nNum < (opt.minNumbers || 15)) return { usable: false, reason: "trang không có lớp chữ đủ dùng (" + runs.length + " mảnh chữ, " + nNum + " số) — OCR ảnh", nNum: nNum };
    var wm = median(runs.map(function (r) { return r.x1 - r.x0; }));
    var cells = runs.map(function (r, i) {
      var num = G.parseCellNumber(r.str), n = typeof num === "number" && isFinite(num) ? num : (/[A-Za-zÀ-ỹ]/.test(r.str) ? null : NaN);
      var c = { id: i, x0: r.x0, y0: r.y0, x1: r.x1, y1: r.y1, cx: (r.x0 + r.x1) / 2, cy: (r.y0 + r.y1) / 2, wide: r.x1 - r.x0 > wm * 2.2, ink: true, bb: { x0: r.x0, y0: r.y0, x1: r.x1, y1: r.y1 }, text: r.str, conf: 100, num: n, src: "pdf" };
      return c;
    });
    var sn = snapToGrid(cells); cells = sn.table;
    var table; try { table = TP.parse(cells); } catch (e) { return { usable: false, reason: "không dựng được bảng từ lớp chữ: " + e.message, nNum: nNum }; }
    if (!table || !table.layout || !(table.lines || []).length) return { usable: false, reason: "lớp chữ không có dạng bảng chấm công — OCR ảnh", nNum: nNum };
    var period = ""; sn.loose.concat(cells.slice(0, 6)).forEach(function (c) { period = period || TP.periodFromText(c.text); });
    var top = sn.loose.filter(function (c) { return c.cy < cells.reduce(function (m, x) { return Math.min(m, x.y0); }, 1e9); }).sort(function (a, b) { return a.cy - b.cy || a.x0 - b.x0; }).map(function (c) { return c.text; });
    return { usable: true, cells: cells, table: table, title: top, period: period, nNum: nNum, box: { x0: Math.min.apply(null, cells.map(function (c) { return c.x0; })), y0: Math.min.apply(null, cells.map(function (c) { return c.y0; })), x1: Math.max.apply(null, cells.map(function (c) { return c.x1; })), y1: Math.max.apply(null, cells.map(function (c) { return c.y1; })) } };
  }
  var API = { analyze: analyze, mergeRuns: mergeRuns, toRect: toRect };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else { root.HAKCore = root.HAKCore || {}; root.HAKCore.pdfText = API; }
})(typeof self !== "undefined" ? self : this);
