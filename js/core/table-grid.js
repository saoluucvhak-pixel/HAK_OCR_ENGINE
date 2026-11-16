// ===== CORE / TABLE-GRID — tìm lưới bảng (đường kẻ ngang / dọc) trong ảnh bảng chấm công (2.0-α20) =====
// JS thuần trên mảng điểm ảnh xám (không phụ thuộc trình duyệt) → chạy được cả trong app và trong test Node.
// Các bước: xám → nhị phân (ngưỡng thích nghi) → chỉnh nghiêng nhỏ → tìm đường kẻ ngang/dọc → các ô (có xét ô gộp ở dòng tiêu đề).
// Chỉ ĐỌC ảnh; kết quả OCR luôn qua bảng xem trước để người dùng sửa trước khi ghi vào dữ liệu.
(function (root) {
  "use strict";

  /** RGBA (Uint8ClampedArray) → xám Uint8Array */
  function toGray(rgba, w, h) {
    var g = new Uint8Array(w * h);
    for (var i = 0, j = 0; i < g.length; i++, j += 4) g[i] = (rgba[j] * 299 + rgba[j + 1] * 587 + rgba[j + 2] * 114) / 1000;
    return g;
  }
  /** Ảnh tích phân (để tính trung bình cửa sổ nhanh) */
  function integral(g, w, h) {
    var s = new Float64Array((w + 1) * (h + 1));
    for (var y = 1; y <= h; y++) { var row = 0; for (var x = 1; x <= w; x++) { row += g[(y - 1) * w + x - 1]; s[y * (w + 1) + x] = s[(y - 1) * (w + 1) + x] + row; } }
    return s;
  }
  /** Nhị phân thích nghi (kiểu Bradley): điểm tối hơn trung bình vùng lân cận k% → mực (1). Chịu được ảnh chụp sáng không đều. */
  function binarize(g, w, h, opt) {
    opt = opt || {};
    var r = opt.radius || Math.max(8, Math.round(Math.min(w, h) / 40)), t = opt.t == null ? 0.15 : opt.t, s = integral(g, w, h), b = new Uint8Array(w * h), W = w + 1;
    for (var y = 0; y < h; y++) {
      var y0 = Math.max(0, y - r), y1 = Math.min(h - 1, y + r);
      for (var x = 0; x < w; x++) {
        var x0 = Math.max(0, x - r), x1 = Math.min(w - 1, x + r), n = (x1 - x0 + 1) * (y1 - y0 + 1);
        var sum = s[(y1 + 1) * W + x1 + 1] - s[y0 * W + x1 + 1] - s[(y1 + 1) * W + x0] + s[y0 * W + x0];
        b[y * w + x] = g[y * w + x] * n < sum * (1 - t) ? 1 : 0;
      }
    }
    return b;
  }
  /** Xoay 90° (k = 1: theo chiều kim đồng hồ, 2: 180°, 3: ngược chiều) — ảnh chụp bảng nằm ngang */
  function rotate90(g, w, h, k) {
    k = ((k % 4) + 4) % 4; if (!k) return { g: g, w: w, h: h };
    var W = k % 2 ? h : w, H = k % 2 ? w : h, o = new Uint8Array(W * H);
    for (var y = 0; y < h; y++) for (var x = 0; x < w; x++) {
      var nx, ny;
      if (k === 1) { nx = h - 1 - y; ny = x; } else if (k === 2) { nx = w - 1 - x; ny = h - 1 - y; } else { nx = y; ny = w - 1 - x; }
      o[ny * W + nx] = g[y * w + x];
    }
    return { g: o, w: W, h: H };
  }
  /** Tỷ lệ mực trong ô (bỏ viền ~inset) + hộp bao nét mực → dùng để bỏ qua ô trống, cắt sát chữ khi OCR */
  function inkBox(b, w, cell, inset) {
    inset = inset == null ? 0.14 : inset;
    var ix = Math.max(2, Math.round((cell.x1 - cell.x0) * inset)), iy = Math.max(2, Math.round((cell.y1 - cell.y0) * inset));
    var x0 = cell.x0 + ix, x1 = cell.x1 - ix, y0 = cell.y0 + iy, y1 = cell.y1 - iy, n = 0, bx0 = 1e9, by0 = 1e9, bx1 = -1, by1 = -1;
    for (var y = y0; y < y1; y++) for (var x = x0; x < x1; x++) if (b[y * w + x]) { n++; if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; if (y < by0) by0 = y; if (y > by1) by1 = y; }
    var area = Math.max(1, (x1 - x0) * (y1 - y0));
    return { ratio: n / area, n: n, box: n ? { x0: bx0, y0: by0, x1: bx1 + 1, y1: by1 + 1 } : null };
  }
  /** Phóng to / thu nhỏ ảnh xám (song tuyến) — ảnh chụp nhỏ được phóng to để ô bảng đủ lớn cho OCR */
  function resize(g, w, h, s) {
    if (!s || s === 1) return { g: g, w: w, h: h };
    var W = Math.max(1, Math.round(w * s)), H = Math.max(1, Math.round(h * s)), o = new Uint8Array(W * H);
    for (var y = 0; y < H; y++) {
      var fy = Math.min(h - 1, y / s), y0 = Math.floor(fy), y1 = Math.min(h - 1, y0 + 1), ty = fy - y0;
      for (var x = 0; x < W; x++) {
        var fx = Math.min(w - 1, x / s), x0 = Math.floor(fx), x1 = Math.min(w - 1, x0 + 1), tx = fx - x0;
        var a0 = g[y0 * w + x0] * (1 - tx) + g[y0 * w + x1] * tx, a1 = g[y1 * w + x0] * (1 - tx) + g[y1 * w + x1] * tx;
        o[y * W + x] = a0 * (1 - ty) + a1 * ty;
      }
    }
    return { g: o, w: W, h: H };
  }
  /** Hệ số phóng để cạnh dài ~ target (mặc định 2400 điểm); ảnh đã đủ lớn thì giữ nguyên */
  function autoScale(w, h, target) { var m = Math.max(w, h); target = target || 2400; return m < target * 0.8 ? target / m : 1; }
  /**
   * Thành phần liên thông của nét mực trong 1 vùng (bỏ chấm nhỏ) — dùng nhận nét "1" viết tay / gạch ghi công
   * mà OCR in ấn hay bỏ sót. Trả [{ x0,y0,x1,y1,n }]
   */
  function inkComponents(b, w, box, minN) {
    var W = box.x1 - box.x0, H = box.y1 - box.y0, seen = new Uint8Array(Math.max(1, W * H)), out = [], st = [];
    minN = minN || Math.max(4, Math.round(W * H * 0.004));
    for (var y = 0; y < H; y++) for (var x = 0; x < W; x++) {
      var i = y * W + x; if (seen[i] || !b[(y + box.y0) * w + x + box.x0]) continue;
      var c = { x0: x, y0: y, x1: x, y1: y, n: 0 }; st.push(i); seen[i] = 1;
      while (st.length) {
        var p = st.pop(), px = p % W, py = (p - px) / W; c.n++;
        if (px < c.x0) c.x0 = px; if (px > c.x1) c.x1 = px; if (py < c.y0) c.y0 = py; if (py > c.y1) c.y1 = py;
        for (var dy = -1; dy <= 1; dy++) for (var dx = -1; dx <= 1; dx++) {
          var nx = px + dx, ny = py + dy; if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          var q = ny * W + nx; if (!seen[q] && b[(ny + box.y0) * w + nx + box.x0]) { seen[q] = 1; st.push(q); }
        }
      }
      if (c.n >= minN) out.push({ x0: c.x0 + box.x0, y0: c.y0 + box.y0, x1: c.x1 + box.x0 + 1, y1: c.y1 + box.y0 + 1, n: c.n });
    }
    return out;
  }
  /**
   * Đếm dấu viết tay trong ô (X, ✓, /): chiếu mực theo cột, mỗi cụm mực cách nhau ≥ 12% chiều cao ô = 1 dấu
   * (bảng chấm công tay "x" = 1 công, "xx" = 2, "xxx" = 3). Cụm quá nhỏ (chấm, vệt) bỏ qua.
   */
  function markGroups(b, w, box) {
    var W = box.x1 - box.x0, H = box.y1 - box.y0; if (W <= 0 || H <= 0) return [];
    var col = new Array(W), x, y;
    for (x = 0; x < W; x++) { var n = 0; for (y = 0; y < H; y++) if (b[(y + box.y0) * w + x + box.x0]) n++; col[x] = n; }
    var runs = [], s = -1, gapMax = Math.max(2, Math.round(H * 0.12));
    for (x = 0; x <= W; x++) {
      var on = x < W && col[x] > 0;
      if (on && s < 0) s = x;
      if (!on && s >= 0) { runs.push([s, x]); s = -1; }
    }
    var groups = [];
    runs.forEach(function (r) { var g = groups[groups.length - 1]; if (g && r[0] - g[1] < gapMax) g[1] = r[1]; else groups.push([r[0], r[1]]); });
    return groups.filter(function (g) {
      var y0 = H, y1 = -1, ink = 0;
      for (var xx = g[0]; xx < g[1]; xx++) for (var yy = 0; yy < H; yy++) if (b[(yy + box.y0) * w + xx + box.x0]) { ink++; if (yy < y0) y0 = yy; if (yy > y1) y1 = yy; }
      return g[1] - g[0] >= H * 0.15 && y1 - y0 >= H * 0.25 && ink >= H * 0.6;
    });
  }
  /**
   * Số dấu trong ô. unitW = bề rộng 1 dấu điển hình của cả trang (trung vị) → 2 nét của 1 dấu bị tách thì gộp lại,
   * nhiều dấu viết dính nhau thì chia theo bề rộng (xxx dính = 3). Không có unitW = đếm cụm.
   */
  function countMarks(b, w, box, unitW) { return countMarksInfo(b, w, box, unitW).n; }
  /** { n, sure }: sure = false khi không thấy dấu nào, hoặc một cụm dính có bề rộng lưng chừng giữa 2 số dấu (vd 1,5 dấu) → tô vàng để người dùng xem lại */
  function countMarksInfo(b, w, box, unitW) {
    var g = markGroups(b, w, box);
    if (!unitW || !g.length) return { n: g.length, sure: g.length > 0 };
    var merged = [], sure = true;
    g.forEach(function (x) { var m = merged[merged.length - 1]; if (m && x[1] - m[0] <= unitW * 1.35) m[1] = x[1]; else merged.push([x[0], x[1]]); });
    var n = merged.reduce(function (s0, x) {
      var r = (x[1] - x[0]) / unitW, k = Math.max(1, Math.round(r)), f = r - Math.floor(r);
      if (r > 1.3 && f > 0.3 && f < 0.7) sure = false;
      return s0 + k;
    }, 0);
    return { n: n, sure: sure };
  }
  /** Ô "7h → 15h" / "7 - 9h" / "22h-6h": số giờ (qua đêm cộng 24), không phải khoảng giờ → null */
  function parseHours(t) {
    var m = String(t || "").replace(/\s+/g, "").match(/(\d{1,2})(?:[h:g](\d{0,2}))?[-–—>→~]+[>]?(\d{1,2})(?:[h:g](\d{0,2}))?/i);
    if (!m) return null;
    var a = +m[1] + (+m[2] || 0) / 60, b2 = +m[3] + (+m[4] || 0) / 60; if (a > 24 || b2 > 24) return null;
    var d = b2 - a; if (d <= 0) d += 24; return d > 0 && d <= 16 ? Math.round(d * 100) / 100 : null;
  }
  /** Ô lịch làm theo ca: "1", "2", "3" = 1 ca; "1+2" = 2 ca … → số ca (= số công); rỗng → null; không đọc được → NaN */
  function parseShifts(t) {
    var s = String(t == null ? "" : t).replace(/\s+/g, "").replace(/[lI|!\]\[jJ]/g, "1");
    if (!s) return null;
    var parts = s.split(/[+&,;]+/).filter(Boolean);
    if (parts.length && parts.every(function (p) { return /^[1-3]$/.test(p); })) return parts.length;
    return NaN;
  }
  /** Ô chỉ có 1 nét đứng mảnh (cao ≥ 2,2 × rộng, cao ≥ 35% ô) → coi là số 1 viết tay */
  function looksLikeOne(comps, cellH) {
    if (comps.length !== 1) return false;
    var c = comps[0], cw = c.x1 - c.x0, ch = c.y1 - c.y0;
    return ch >= cw * 2.2 && ch >= cellH * 0.35;
  }
  /** Chuẩn hóa chữ số OCR của 1 ô công / cơm: "1", "0,5", "0.5", "2", "1/2" → số; rỗng → null; đọc không ra → NaN */
  function parseCellNumber(t) {
    var s = String(t == null ? "" : t).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, "").replace(/[Oo]/g, "0").replace(/[lI|!\]\[jJ]/g, "1").replace(/[Ss]/g, "5").replace(/[Zz]/g, "2").replace(/,/g, ".").replace(/^\.(?=\d)/, "0.").replace(/^[.\-_~'"`]+|[.\-_~'"`]+$/g, "");
    if (!s) return null;
    if (s === "1/2" || s === "½") return 0.5;
    var m = s.match(/^\d+(\.\d+)?$/); if (m) return parseFloat(s);
    var m2 = s.match(/(\d+(\.\d+)?)/); return m2 ? parseFloat(m2[1]) : NaN;
  }
  /**
   * Bám theo đường kẻ (cho phép lệch ±1 điểm mỗi bước, đứt ≤ gap) → chịu được ảnh chụp nghiêng / méo phối cảnh nhẹ.
   * horiz = true: đường ngang; trả [{ pts: [[x,y]…], len, a, b }] (a,b = đầu / cuối theo trục chính)
   */
  function traceLines(b, w, h, horiz, minLen, gap) {
    gap = gap || 3;
    var seen = new Uint8Array(w * h), out = [], L = horiz ? w : h, M = horiz ? h : w;
    var ink = function (u, v) { if (u < 0 || v < 0 || u >= L || v >= M) return 0; return horiz ? b[v * w + u] : b[u * w + v]; };
    var mark = function (u, v) { for (var d = -2; d <= 2; d++) { var vv = v + d; if (vv >= 0 && vv < M && u >= 0 && u < L) seen[horiz ? vv * w + u : u * w + vv] = 1; } };
    var isSeen = function (u, v) { return seen[horiz ? v * w + u : u * w + v]; };
    for (var v0 = 0; v0 < M; v0 += 1) for (var u0 = 0; u0 < L; u0++) {
      if (!ink(u0, v0) || isSeen(u0, v0)) continue;
      // nhanh: cần ít nhất 8 điểm mực liên tiếp mới bắt đầu bám
      var k = 0; while (k < 8 && ink(u0 + k, v0)) k++; if (k < 8) continue;
      var pts = [], u = u0, v = v0, miss = 0, last = u0;
      while (u < L) {
        var nv = ink(u, v) ? v : ink(u, v - 1) ? v - 1 : ink(u, v + 1) ? v + 1 : -1;
        if (nv >= 0) { v = nv; miss = 0; last = u; if (!(u % 4)) pts.push([u, v]); mark(u, v); }
        else if (++miss > gap) break;
        u++;
      }
      if (last - u0 >= minLen) { if (pts.length && pts[pts.length - 1][0] !== last) pts.push([last, v]); out.push({ pts: pts, len: last - u0, a: u0, b: last }); }
    }
    // nối các đoạn cùng 1 đường bị đứt (đầu–cuối gần nhau, cùng cao độ)
    out.sort(function (p, q) { return p.a - q.a; });
    var merged = [];
    out.forEach(function (s) {
      var vS = s.pts[0][1];
      for (var i = 0; i < merged.length; i++) {
        var m = merged[i], vE = m.pts[m.pts.length - 1][1];
        if (s.a - m.b <= Math.max(12, L * 0.02) && s.a >= m.b - 4 && Math.abs(vS - vE) <= 4) { m.pts = m.pts.concat(s.pts); m.b = Math.max(m.b, s.b); m.len = m.b - m.a; return; }
      }
      merged.push({ pts: s.pts.slice(), len: s.len, a: s.a, b: s.b });
    });
    return merged.map(function (m) { return horiz ? m : { pts: m.pts.map(function (p) { return [p[1], p[0]]; }), len: m.len, a: m.a, b: m.b }; });
  }
  /** Vẽ các đường đã bám thành mặt nạ (dày t, kéo dài 2 đầu ext điểm để khép kín góc ô) */
  function drawLines(lines, w, h, horiz, t, ext) {
    var m = new Uint8Array(w * h);
    lines.forEach(function (ln) {
      var pts = ln.pts.slice();
      if (!pts.length) return;
      var f = pts[0], l = pts[pts.length - 1];
      if (horiz) { pts.unshift([Math.max(0, f[0] - ext), f[1]]); pts.push([Math.min(w - 1, l[0] + ext), l[1]]); }
      else { pts.unshift([f[0], Math.max(0, f[1] - ext)]); pts.push([l[0], Math.min(h - 1, l[1] + ext)]); }
      for (var i = 1; i < pts.length; i++) {
        var p = pts[i - 1], q = pts[i], n = Math.max(Math.abs(q[0] - p[0]), Math.abs(q[1] - p[1]), 1);
        for (var s = 0; s <= n; s++) {
          var x = Math.round(p[0] + (q[0] - p[0]) * s / n), y = Math.round(p[1] + (q[1] - p[1]) * s / n);
          for (var d = -t; d <= t; d++) { var xx = horiz ? x : x + d, yy = horiz ? y + d : y; if (xx >= 0 && yy >= 0 && xx < w && yy < h) m[yy * w + xx] = 1; }
        }
      }
    });
    return m;
  }
  /**
   * Các ô của bảng = vùng trống liên thông giữa các đường kẻ (ô gộp ngang / dọc tự ra 1 ô).
   * Trả { cells: [{ x0,y0,x1,y1, cx, cy, area }], box: khung bảng, h: đường ngang, v: đường dọc }
   */
  function findCells(b, w, h, opt) {
    opt = opt || {};
    var hl = traceLines(b, w, h, true, opt.minH || Math.round(w * 0.12)), vl = traceLines(b, w, h, false, opt.minV || Math.round(h * 0.03));
    var maxH = hl.reduce(function (a, l) { return Math.max(a, l.len); }, 0), maxV = vl.reduce(function (a, l) { return Math.max(a, l.len); }, 0);
    hl = hl.filter(function (l) { return l.len >= maxH * (opt.hFrac || 0.25); }); vl = vl.filter(function (l) { return l.len >= maxV * (opt.vFrac || 0.2); });
    if (!hl.length || !vl.length) return { cells: [], box: null, h: hl, v: vl };
    var t = opt.thick || 1, ext = opt.ext || Math.max(6, Math.round(Math.min(w, h) * 0.006));
    var hm = drawLines(hl, w, h, true, t, ext), vm = drawLines(vl, w, h, false, t, ext), m = new Uint8Array(w * h);
    for (var i = 0; i < m.length; i++) m[i] = hm[i] | vm[i];
    // khung bảng = hộp bao của các đường dài nhất
    var bx0 = w, by0 = h, bx1 = 0, by1 = 0;
    hl.concat(vl).forEach(function (l) { l.pts.forEach(function (p) { bx0 = Math.min(bx0, p[0]); by0 = Math.min(by0, p[1]); bx1 = Math.max(bx1, p[0]); by1 = Math.max(by1, p[1]); }); });
    // gán nhãn vùng trống trong khung (4 lân cận)
    var lab = new Int32Array(w * h), cells = [], q = new Int32Array(w * h), id = 0;
    for (var y = by0; y <= by1; y++) for (var x = bx0; x <= bx1; x++) {
      var p0 = y * w + x; if (m[p0] || lab[p0]) continue;
      id++; var qh = 0, qt = 0, cx0 = x, cy0 = y, cx1 = x, cy1 = y, n = 0, edge = false; q[qt++] = p0; lab[p0] = id;
      while (qh < qt) {
        var p = q[qh++], px = p % w, py = (p - px) / w; n++;
        if (px < cx0) cx0 = px; if (px > cx1) cx1 = px; if (py < cy0) cy0 = py; if (py > cy1) cy1 = py;
        if (px <= bx0 || px >= bx1 || py <= by0 || py >= by1) edge = true;
        var nb = [p - 1, p + 1, p - w, p + w];
        for (var k = 0; k < 4; k++) { var r = nb[k]; if (r < 0 || r >= w * h) continue; var rx = r % w, ry = (r - rx) / w; if (rx < bx0 || rx > bx1 || ry < by0 || ry > by1) continue; if (!m[r] && !lab[r]) { lab[r] = id; q[qt++] = r; } }
      }
      if (!edge) cells.push({ x0: cx0, y0: cy0, x1: cx1 + 1, y1: cy1 + 1, cx: (cx0 + cx1) / 2, cy: (cy0 + cy1) / 2, area: n });
    }
    // bỏ vùng quá nhỏ (khe giữa 2 nét kẻ đôi)
    var areas = cells.map(function (c) { return c.area; }).sort(function (a, b2) { return a - b2; }), med = areas.length ? areas[Math.floor(areas.length / 2)] : 0;
    cells = cells.filter(function (c) { return c.area >= med * 0.15 && (c.x1 - c.x0) >= 4 && (c.y1 - c.y0) >= 4; });
    return { cells: cells, box: { x0: bx0, y0: by0, x1: bx1, y1: by1 }, h: hl, v: vl, mask: m };
  }
  /**
   * Xóa đường kẻ khỏi ảnh (để ô cắt ra chỉ còn chữ / số): điểm mực nằm sát đường kẻ đã bám (± t điểm) → trắng.
   * Trả { g: ảnh xám sạch, b: nhị phân sạch }
   */
  function removeLines(g, b, w, h, found, t) {
    t = t == null ? 2 : t;
    var hm = drawLines(found.h || [], w, h, true, t, 2), vm = drawLines(found.v || [], w, h, false, t, 2), g2 = new Uint8Array(g), b2 = new Uint8Array(b);
    for (var i = 0; i < g2.length; i++) if (hm[i] || vm[i]) { g2[i] = 255; b2[i] = 0; }
    return { g: g2, b: b2 };
  }
  var api = { toGray: toGray, binarize: binarize, rotate90: rotate90, traceLines: traceLines, drawLines: drawLines, findCells: findCells, removeLines: removeLines, resize: resize, autoScale: autoScale, inkComponents: inkComponents, countMarks: countMarks, countMarksInfo: countMarksInfo, markGroups: markGroups, parseHours: parseHours, parseShifts: parseShifts, looksLikeOne: looksLikeOne, inkBox: inkBox, parseCellNumber: parseCellNumber };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else { root.HAKCore = root.HAKCore || {}; root.HAKCore.grid = api; }
})(typeof window !== "undefined" ? window : this);
