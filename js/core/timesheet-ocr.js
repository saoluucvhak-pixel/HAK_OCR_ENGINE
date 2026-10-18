// ===== CORE / TIMESHEET-OCR — đọc 1 ảnh bảng chấm công / chấm cơm → bảng xem trước (2.0-α20) =====
// Điều phối: phóng ảnh nhỏ → đoán chiều ảnh (thử 4 hướng trên vài ô chữ) → tìm ô (core/table-grid) → cắt từng ô
// → OCR theo lô (host.ocr: Tesseract chạy offline ở tiến trình chính) → dựng bảng (core/timesheet-parse).
// Ô 1 nét đứng mảnh mà OCR không đọc ra (hoặc đọc nhầm thành "0") → coi là "1" viết tay (đánh dấu cần kiểm tra).
(function (root) {
  "use strict";
  var NODE = typeof module !== "undefined" && module.exports;
  var G = NODE ? require("./table-grid.js") : root.HAKCore.grid;
  var TP = NODE ? require("./timesheet-parse.js") : root.HAKCore.tsparse;

  /** Cắt vùng (x0,y0,x1,y1) của ảnh xám, phóng cao ~targetH, viền trắng pad; k = xoay 90° (đoán chiều) */
  function crop(g, w, h, r, targetH, pad, k) {
    var x0 = Math.max(0, Math.floor(r.x0)), y0 = Math.max(0, Math.floor(r.y0)), x1 = Math.min(w, Math.ceil(r.x1)), y1 = Math.min(h, Math.ceil(r.y1));
    var cw = Math.max(1, x1 - x0), ch = Math.max(1, y1 - y0), sub = new Uint8Array(cw * ch);
    for (var y = 0; y < ch; y++) for (var x = 0; x < cw; x++) sub[y * cw + x] = g[(y + y0) * w + x + x0];
    var rot = G.rotate90(sub, cw, ch, k || 0), s = Math.min(6, Math.max(1, targetH / rot.h)), z = G.resize(rot.g, rot.w, rot.h, s);
    pad = pad == null ? 10 : pad;
    var W = z.w + 2 * pad, H = z.h + 2 * pad, o = new Uint8Array(W * H).fill(255);
    var hist = new Uint32Array(256), n = z.w * z.h, lo = 255;
    for (var i = 0; i < n; i++) { hist[z.g[i]]++; if (z.g[i] < lo) lo = z.g[i]; }
    var acc = 0, hi = 255; for (var v = 0; v < 256; v++) { acc += hist[v]; if (acc >= n * 0.6) { hi = v; break; } } // nền ≈ phân vị 60%
    var cut = hi - (hi - lo) * 0.15, span = Math.max(1, cut - lo);
    // kéo giãn tương phản: nền (xám nhạt, nhiễu nén JPEG / khử răng cưa của PDF) → trắng; nét → đậm. Tesseract đọc ô 1 chữ số kém nếu nền không sạch.
    for (y = 0; y < z.h; y++) for (x = 0; x < z.w; x++) { var g0 = z.g[y * z.w + x]; o[(y + pad) * W + x + pad] = hi - lo < 40 ? g0 : g0 >= cut ? 255 : Math.round((g0 - lo) / span * 255); }
    return { w: W, h: H, data: o };
  }
  function letters(t) { return (String(t || "").match(/[A-Za-zÀ-ỹ]/g) || []).length; }
  function prepCells(b, w, cells, medW) {
    return cells.map(function (c, i) {
      var cw = c.x1 - c.x0, ch = c.y1 - c.y0, wide = cw > medW * 2.2;
      var insX = Math.max(2, Math.min(wide ? 5 : 99, Math.round(cw * 0.08))), insY = Math.max(2, Math.round(ch * 0.1));
      var inner = { x0: c.x0 + insX, x1: c.x1 - insX, y0: c.y0 + insY, y1: c.y1 - insY };
      var ib = inner.x1 > inner.x0 && inner.y1 > inner.y0 ? G.inkBox(b, w, inner, 0) : { n: 0, box: null };
      // Ảnh chụp nghiêng / cong: đường kẻ ngang không bị xóa hết, còn sót vệt dài trong ô → hộp mực kéo giãn cả ô, Tesseract đọc "1" thành "2", "4"…
      // Chỉ giữ các cụm mực KHÔNG giống vệt kẻ (dài ngang, mỏng); hộp mực = hợp của các cụm còn lại.
      if (ib.box) {
        var iw = inner.x1 - inner.x0, ih = inner.y1 - inner.y0, all = G.inkComponents(b, w, inner, 8), keep = all.filter(function (k) {
          var kw = k.x1 - k.x0, kh = k.y1 - k.y0;
          return !(kw > 4 * kh || kh <= 2 || (kw >= 0.6 * iw && kh <= 0.25 * ih));
        });
        // có cụm giống chữ/số thì bỏ các vệt kẻ; chỉ toàn vệt dài (VD ô ghi "-") → giữ nguyên hộp mực cũ
        if (keep.length && keep.length < all.length) {
          var ux0 = 1e9, uy0 = 1e9, ux1 = -1, uy1 = -1, un = 0;
          keep.forEach(function (k) { ux0 = Math.min(ux0, k.x0); uy0 = Math.min(uy0, k.y0); ux1 = Math.max(ux1, k.x1); uy1 = Math.max(uy1, k.y1); un += k.n; });
          ib = { n: un, box: { x0: ux0, y0: uy0, x1: ux1, y1: uy1 } };
        }
      }
      var ink = !!ib.box && ib.n >= Math.max(6, cw * ch * 0.004);
      var bb = ink ? { x0: Math.max(c.x0 + 1, ib.box.x0 - 3), x1: Math.min(c.x1 - 1, ib.box.x1 + 3), y0: Math.max(c.y0 + 1, ib.box.y0 - 3), y1: Math.min(c.y1 - 1, ib.box.y1 + 3) } : null;
      if (bb) { var need = Math.round((bb.y1 - bb.y0) * 0.7) - (bb.x1 - bb.x0); if (need > 0) { bb.x0 = Math.max(c.x0 + 1, bb.x0 - Math.ceil(need / 2)); bb.x1 = Math.min(c.x1 - 1, bb.x1 + Math.ceil(need / 2)); } } // nét "1" mảnh: nới ngang để OCR không báo ảnh quá nhỏ
      return { id: i, x0: c.x0, y0: c.y0, x1: c.x1, y1: c.y1, cx: c.cx, cy: c.cy, wide: wide, ink: ink, bb: bb, text: "", conf: 0, num: null, src: "" };
    });
  }
  /** Đoán chiều ảnh: đọc thử cả trang (≤ 2000 điểm, ảnh nhỏ đã được phóng to trước) ở 4 hướng, chọn hướng có nhiều từ đọc chắc nhất */
  function guessRotation(g, w, h, b, ocr) {
    var s = Math.min(1, 2000 / Math.max(w, h)), z = G.resize(g, w, h, s), items = [];
    [0, 1, 2, 3].forEach(function (k) { var r = G.rotate90(z.g, z.w, z.h, k); items.push({ w: r.w, h: r.h, data: r.g, mode: "page", k: k }); });
    return ocr(items).then(function (out) {
      var best = 0; out.forEach(function (r, k) { if ((r.good || 0) > (out[best].good || 0)) best = k; });
      return (out[0].good || 0) >= (out[best].good || 0) * 0.85 ? 0 : best; // gần bằng nhau → giữ nguyên (đa số ảnh đã đúng chiều)
    });
  }
  /** Dòng chữ phía trên bảng (tiêu đề: "BẢNG CHẤM CÔNG …", "Tháng 09/2026") */
  function titleLines(b, w, h, box, maxLines) {
    if (!box) return [];
    var y1 = Math.max(0, box.y0 - 2), y0 = Math.max(0, box.y0 - Math.round(Math.max(h * 0.18, 320))), prof = []; // tiêu đề có thể cách bảng khá xa, rộng hơn bảng
    for (var y = y0; y < y1; y++) { var n = 0; for (var x = 0; x < w; x += 2) if (b[y * w + x]) n++; prof.push(n); }
    var thr = Math.max(2, (box.x1 - box.x0) * 0.004), lines = [], s = -1;
    for (var i = 0; i <= prof.length; i++) { var on = i < prof.length && prof[i] >= thr; if (on && s < 0) s = i; if (!on && s >= 0) { if (i - s >= 6) lines.push({ y0: y0 + s - 2, y1: y0 + i + 2 }); s = -1; } }
    return lines.slice(-(maxLines || 4)).map(function (l) {
      var x0 = w, x1 = 0;
      for (var y = l.y0; y < l.y1; y++) for (var x = 0; x < w; x++) if (b[y * w + x]) { if (x < x0) x0 = x; if (x > x1) x1 = x; }
      return { x0: Math.max(0, x0 - 4), x1: Math.min(w, x1 + 4), y0: Math.max(0, l.y0), y1: Math.min(h, l.y1) };
    }).filter(function (r) { return r.x1 > r.x0; });
  }
  /**
   * Cách đọc ô ngày (α22, chủ sở hữu duyệt 11/10/2026):
   *  "mark" — bảng đánh dấu: x = 1 công, xx = 2, xxx = 3; ô ghi giờ "7h→15h" = số giờ / 8
   *  "ca"   — lịch làm theo ca: "1" / "2" / "3" = 1 công, "1+2" = 2 công, X = nghỉ
   * Đặt c.val cho mọi ô có mực (timesheet-parse dùng c.val cho ô ngày; cột ngày vẫn nhận theo c.num).
   */
  function cellMode(cells, clean, r, mode, host) {
    if (mode !== "mark" && mode !== "ca") return Promise.resolve();
    var ink = cells.filter(function (c) { return c.ink && c.bb; });
    var items = ink.map(function (c) { return Object.assign(crop(clean.g, r.w, r.h, c.bb, 40, 10, 0), { mode: mode === "ca" ? "ca" : "block" }); });
    return (items.length ? host.ocr(items) : Promise.resolve([])).then(function (out) {
      // bề rộng 1 dấu điển hình của trang (trung vị các cụm mực) — chuẩn hóa đếm "xxx"
      var widths = []; if (mode === "mark") ink.forEach(function (c) { G.markGroups(clean.b, r.w, c.bb).forEach(function (g) { widths.push(g[1] - g[0]); }); });
      widths.sort(function (a, b) { return a - b; });
      var unitW = widths.length >= 5 ? widths[Math.floor(widths.length / 2)] : 0;
      ink.forEach(function (c, i) {
        var t = (out[i] || {}).text || "", conf = (out[i] || {}).conf || 0;
        if (mode === "mark") {
          var hr = G.parseHours(t) != null ? G.parseHours(t) : G.parseHours(c.text);
          if (hr != null) { c.val = Math.round(hr / 8 * 1000) / 1000; c.valSrc = "giờ " + hr; return; }
          var mi = G.countMarksInfo(clean.b, r.w, c.bb, unitW), n = mi.n;
          c.val = n > 0 ? n : NaN; c.valSrc = n > 0 ? n + " dấu" : "không rõ"; c.unsure = !mi.sure;
        } else {
          var v = G.parseShifts(t);
          if (!(typeof v === "number" && isFinite(v))) v = G.parseShifts(c.text);
          if (typeof v === "number" && isFinite(v)) { c.val = v; c.valSrc = v + " ca"; return; }
          if (/[xX×]/.test(t)) { c.val = null; c.valSrc = "X = nghỉ"; return; }
          if (G.looksLikeOne(G.inkComponents(clean.b, r.w, c.bb), c.y1 - c.y0)) { c.val = 1; c.valSrc = "nét 1"; c.unsure = true; return; }
          c.val = NaN; c.valSrc = "không rõ (" + t + ")";
        }
        c.conf = Math.min(c.conf || conf, conf);
      });
    });
  }
  /**
   * img: { g: xám Uint8Array, w, h }; host.ocr(items) → Promise<[{ text, conf }]>; opt.rotate: 0…3 (bỏ trống = tự đoán); opt.onProgress(msg)
   * Trả Promise<{ rot, scale, g, w, h, cells, table, title, period }>
   */
  function analyze(img, host, opt) {
    opt = opt || {};
    var say = opt.onProgress || function () {};
    var s = opt.scale || G.autoScale(img.w, img.h, opt.target || 2400), z = G.resize(img.g, img.w, img.h, s);
    var b0 = G.binarize(z.g, z.w, z.h);
    say("Đang xác định chiều ảnh…");
    var pRot = opt.rotate != null ? Promise.resolve(opt.rotate) : guessRotation(z.g, z.w, z.h, b0, host.ocr);
    return pRot.then(function (k) {
      var r = G.rotate90(z.g, z.w, z.h, k), b = k ? G.binarize(r.g, r.w, r.h) : b0;
      say("Đang tìm ô của bảng…");
      var found = G.findCells(b, r.w, r.h), clean = G.removeLines(r.g, b, r.w, r.h, found, 2);
      var ws = found.cells.map(function (c) { return c.x1 - c.x0; }).sort(function (a, x) { return a - x; }), medW = ws[Math.floor(ws.length / 2)] || 10;
      var cells = prepCells(clean.b, r.w, found.cells, medW), todo = cells.filter(function (c) { return c.ink; });
      var tl = titleLines(b, r.w, r.h, found.box, 4);
      say("Đang đọc " + todo.length + " ô có chữ / số…");
      var items = todo.map(function (c) { return Object.assign(crop(clean.g, r.w, r.h, c.bb, 40, 10, 0), { mode: c.wide ? "text" : "digit" }); })
        .concat(tl.map(function (t) { return Object.assign(crop(r.g, r.w, r.h, t, 36, 8, 0), { mode: "text" }); }));
      return host.ocr(items).then(function (out) {
        todo.forEach(function (c, i) { c.text = out[i].text; c.conf = out[i].conf; c.handwriting = out[i].handwriting || null; c.src = c.wide ? "text" : "digit"; });
        var title = tl.map(function (t, i) { return out[todo.length + i].text; }).filter(Boolean);
        // ô hẹp đọc số không chắc → đọc lại dạng chữ (tiêu đề "Tổng công", nhãn "Công / Tăng ca")
        // ô rộng đọc 1 dòng không chắc (nhãn 2 dòng "Tổng / công") → đọc lại dạng khối
        // ô hẹp mà vệt mực dài như 1 dòng chữ (tên người ở tiêu đề cột) nhưng đọc số chỉ ra 1 chữ số → đọc lại dạng chữ
        var textLike = function (c) { return !c.wide && c.bb && c.bb.x1 - c.bb.x0 > 3 * (c.bb.y1 - c.bb.y0) && String(c.text).replace(/[^0-9]/g, "").length <= 1; };
        var again = todo.filter(function (c) { return c.conf < 55 || !String(c.text).trim() || textLike(c); });
        // ô rộng (cột "Tổng công") có thể chỉ chứa số → đọc thêm dạng số
        var items2 = [];
        again.forEach(function (c) {
          var im = crop(clean.g, r.w, r.h, c.bb, 40, 10, 0);
          items2.push(Object.assign({}, im, { mode: "block" }));
          if (c.wide) items2.push(Object.assign({}, im, { mode: "digit" }));
        });
        return (items2.length ? host.ocr(items2) : Promise.resolve([])).then(function (o2) {
          var j = 0;
          again.forEach(function (c) {
            var t2 = o2[j++] || { text: "", conf: 0 }, td = c.wide ? o2[j++] || { text: "", conf: 0 } : null;
            var n1 = G.parseCellNumber(c.text), num1 = typeof n1 === "number" && isFinite(n1);
            if (c.wide) {
              var nd = G.parseCellNumber(td.text), numD = typeof nd === "number" && isFinite(nd);
              if (letters(t2.text) >= 3 && t2.conf > c.conf) { c.text = t2.text; c.conf = t2.conf; }
              else if (numD && td.conf >= 50 && letters(c.text) <= 1 && letters(t2.text) <= 1) { c.text = td.text; c.conf = td.conf; c.src = "digit"; }
              else if (t2.conf > c.conf && letters(t2.text) >= letters(c.text)) { c.text = t2.text; c.conf = t2.conf; }
              return;
            }
            if ((letters(t2.text) >= 3 || /^\s*t[cg]\s*$/i.test(t2.text)) && t2.conf >= 45 && (!num1 || (textLike(c) && letters(t2.text) >= 4))) { c.text = t2.text; c.conf = t2.conf; c.src = "text"; } // nhãn chữ (Tổng công, Tăng ca…) — ô số giữ kết quả số
          });
          cells.forEach(function (c) {
            if (!c.ink) { c.num = null; return; }
            var n = G.parseCellNumber(c.text);
            if ((n == null || isNaN(n) || n === 0) && c.src === "digit" && G.looksLikeOne(G.inkComponents(clean.b, r.w, c.bb), c.y1 - c.y0)) { n = 1; c.text = "1"; c.conf = 40; c.src = "nét"; }
            if (!c.wide && typeof n === "number" && n > 31) n = NaN; // ô hẹp > 31 (không phải ngày, không thể là công 1 ngày) = đọc sai → "?"
            c.num = n == null ? (letters(c.text) ? null : NaN) : n;
          });
          return cellMode(cells, clean, r, opt.cellMode, host).then(function () {
          say("Đang dựng bảng…");
          var table = TP.parse(cells.map(function (c) { return c; }));
          var period = ""; title.forEach(function (t) { period = period || TP.periodFromText(t); });
          return { rot: k, scale: s, g: r.g, clean: clean.g, w: r.w, h: r.h, cells: cells, table: table, title: title, period: period, box: found.box, cellMode: opt.cellMode || "so" };
          });
        });
      });
    });
  }
  var api = { analyze: analyze, crop: crop, guessRotation: guessRotation };
  if (NODE) module.exports = api;
  else { root.HAKCore = root.HAKCore || {}; root.HAKCore.tsocr = api; }
})(typeof window !== "undefined" ? window : this);
