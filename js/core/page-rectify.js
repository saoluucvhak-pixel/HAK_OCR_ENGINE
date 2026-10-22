// ===== CORE / PAGE-RECTIFY — nắn thẳng CẢ TRANG ảnh chụp bảng chấm công (nghiêng nhỏ + phối cảnh) =====
// Tìm 4 đường viền ngoài của bảng (core/table-grid.traceLines) → khớp đường thẳng → 4 góc → phép biến đổi phối cảnh
// đưa khung bảng về hình chữ nhật, áp cho CẢ trang (giữ tiêu đề, kỳ lương, chữ ký ngoài bảng).
// An toàn: ảnh đã thẳng → trả nguyên ảnh; thiếu đường kẻ / góc lệch quá lớn / khung quá nhỏ → KHÔNG nắn, ghi lý do.
// Kết quả luôn kèm góc, 4 góc nguồn và ma trận để đối chiếu; không tự duyệt dữ liệu OCR.
(function (root) {
  "use strict";
  var NODE = typeof module !== "undefined" && module.exports;
  var G = NODE ? require("./table-grid.js") : root.HAKCore.grid;
  var DEG = 180 / Math.PI;

  /** Khớp đường thẳng bình phương tối thiểu: ngang y = m·x + c; dọc x = m·y + c. */
  function fit(line, horiz) {
    var n = 0, su = 0, sv = 0, suu = 0, suv = 0;
    line.pts.forEach(function (p) { var u = horiz ? p[0] : p[1], v = horiz ? p[1] : p[0]; n++; su += u; sv += v; suu += u * u; suv += u * v; });
    var d = n * suu - su * su; if (n < 4 || !d) return null;
    var m = (n * suv - su * sv) / d;
    return { m: m, c: (sv - m * su) / n, len: line.len, mid: (sv - m * su) / n + m * (su / n) };
  }
  /** Giao của đường ngang y = a·x + b và đường dọc x = c·y + d */
  function meet(hz, vt) { var x = (vt.m * hz.c + vt.c) / (1 - vt.m * hz.m); return [x, hz.m * x + hz.c]; }

  /** Ma trận phối cảnh 3×3 (h33 = 1) đưa 4 điểm from[i] → to[i] (khử Gauss có chọn trụ). */
  function homography(from, to) {
    var A = [], i, j, k;
    for (i = 0; i < 4; i++) {
      var x = from[i][0], y = from[i][1], X = to[i][0], Y = to[i][1];
      A.push([x, y, 1, 0, 0, 0, -x * X, -y * X, X]);
      A.push([0, 0, 0, x, y, 1, -x * Y, -y * Y, Y]);
    }
    for (i = 0; i < 8; i++) {
      var p = i; for (j = i + 1; j < 8; j++) if (Math.abs(A[j][i]) > Math.abs(A[p][i])) p = j;
      if (Math.abs(A[p][i]) < 1e-12) return null;
      var t = A[i]; A[i] = A[p]; A[p] = t;
      for (j = i + 1; j < 8; j++) { var f = A[j][i] / A[i][i]; for (k = i; k < 9; k++) A[j][k] -= f * A[i][k]; }
    }
    var h = new Array(8);
    for (i = 7; i >= 0; i--) { var s = A[i][8]; for (j = i + 1; j < 8; j++) s -= A[i][j] * h[j]; h[i] = s / A[i][i]; }
    return h.concat([1]);
  }
  /** Nội suy bicubic (Catmull-Rom): ảnh đã phóng to song tuyến ở bước trước — nắn thêm 1 lần song tuyến làm nét chữ mờ gấp đôi */
  function cubic(g, w, h, sx, sy) {
    var x0 = Math.floor(sx), y0 = Math.floor(sy), fx = sx - x0, fy = sy - y0, wx = kern(fx), wy = kern(fy), v = 0;
    for (var j = 0; j < 4; j++) {
      var yy = Math.min(h - 1, Math.max(0, y0 - 1 + j)), row = 0;
      for (var i = 0; i < 4; i++) row += wx[i] * g[yy * w + Math.min(w - 1, Math.max(0, x0 - 1 + i))];
      v += wy[j] * row;
    }
    return v;
  }
  function kern(t) { var t2 = t * t, t3 = t2 * t; return [(-t3 + 2 * t2 - t) / 2, (3 * t3 - 5 * t2 + 2) / 2, (-3 * t3 + 4 * t2 + t) / 2, (t3 - t2) / 2]; }
  function apply(H, x, y) { var z = H[6] * x + H[7] * y + 1; return [(H[0] * x + H[1] * y + H[2]) / z, (H[3] * x + H[4] * y + H[5]) / z]; }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }
  function round2(v) { return Math.round(v * 100) / 100; }

  /**
   * g: ảnh xám Uint8Array (w × h). opt: { maxAngle (độ, mặc định 15), minArea (tỷ lệ diện tích khung, 0,05), straightPx (2) }
   * Trả { g, w, h, applied, status, angle?, perspective?, corners?, matrix?, offset? }
   *  status: RECTIFIED | STRAIGHT | NO_TABLE_LINES | ANGLE_OUT_OF_RANGE | TABLE_TOO_SMALL | GEOMETRY_INVALID
   */
  function rectify(g, w, h, opt) {
    opt = opt || {};
    var maxAngle = opt.maxAngle || 15, keep = function (status, extra) { return Object.assign({ g: g, w: w, h: h, applied: false, status: status }, extra || {}); };
    var b = G.binarize(g, w, h);
    var hl = G.traceLines(b, w, h, true, Math.round(w * 0.12)).map(function (l) { return fit(l, true); }).filter(Boolean);
    var vl = G.traceLines(b, w, h, false, Math.round(h * 0.03)).map(function (l) { return fit(l, false); }).filter(Boolean);
    var maxH = hl.reduce(function (a, l) { return Math.max(a, l.len); }, 0), maxV = vl.reduce(function (a, l) { return Math.max(a, l.len); }, 0);
    hl = hl.filter(function (l) { return l.len >= maxH * 0.5; }); vl = vl.filter(function (l) { return l.len >= maxV * 0.5; });
    if (hl.length < 2 || vl.length < 2) return keep("NO_TABLE_LINES");
    // viền bảng = đường ngang trên / dưới cùng, đường dọc trái / phải cùng (so tại tâm ảnh)
    var at = function (l, t) { return l.m * t + l.c; };
    hl.sort(function (p, q) { return at(p, w / 2) - at(q, w / 2); }); vl.sort(function (p, q) { return at(p, h / 2) - at(q, h / 2); });
    var top = hl[0], bot = hl[hl.length - 1], left = vl[0], right = vl[vl.length - 1];
    var angles = [Math.atan(top.m), Math.atan(bot.m), -Math.atan(left.m), -Math.atan(right.m)].map(function (a) { return a * DEG; });
    var angle = (angles[0] + angles[1] + angles[2] + angles[3]) / 4;
    if (angles.some(function (a) { return Math.abs(a) > maxAngle; })) return keep("ANGLE_OUT_OF_RANGE", { angle: round2(angle) });
    var tl = meet(top, left), tr = meet(top, right), br = meet(bot, right), bl = meet(bot, left), quad = [tl, tr, br, bl];
    if (quad.some(function (p) { return !isFinite(p[0]) || !isFinite(p[1]) || p[0] < -w * 0.05 || p[1] < -h * 0.05 || p[0] > w * 1.05 || p[1] > h * 1.05; })) return keep("GEOMETRY_INVALID", { angle: round2(angle) });
    var area = 0; for (var i = 0; i < 4; i++) { var a = quad[i], c = quad[(i + 1) % 4]; area += a[0] * c[1] - c[0] * a[1]; }
    if (Math.abs(area) / 2 < (opt.minArea || 0.05) * w * h) return keep("TABLE_TOO_SMALL", { angle: round2(angle) });
    var dev = Math.max(Math.abs(tl[1] - tr[1]), Math.abs(bl[1] - br[1]), Math.abs(tl[0] - bl[0]), Math.abs(tr[0] - br[0]));
    if (dev <= (opt.straightPx || 2)) return keep("STRAIGHT", { angle: round2(angle) });
    var perspective = Math.abs(angles[0] - angles[1]) > 0.3 || Math.abs(angles[2] - angles[3]) > 0.3;

    // khung đích: hình chữ nhật cùng tâm với khung nguồn, cạnh = cạnh dài hơn của mỗi cặp (không thu nhỏ chữ)
    var RW = Math.max(dist(tl, tr), dist(bl, br)), RH = Math.max(dist(tl, bl), dist(tr, br));
    var cx = (tl[0] + tr[0] + br[0] + bl[0]) / 4, cy = (tl[1] + tr[1] + br[1] + bl[1]) / 4, rx0 = cx - RW / 2, ry0 = cy - RH / 2;
    var rect = [[rx0, ry0], [rx0 + RW, ry0], [rx0 + RW, ry0 + RH], [rx0, ry0 + RH]];
    var fwd = homography(quad, rect), inv = homography(rect, quad);
    if (!fwd || !inv) return keep("GEOMETRY_INVALID", { angle: round2(angle) });
    // khung ra = hộp bao 4 góc trang sau biến đổi, giới hạn trong khung bảng + lề nguồn × 1,15 (phối cảnh không làm phình góc xa)
    var mL = Math.max(0, Math.min(tl[0], bl[0])), mT = Math.max(0, Math.min(tl[1], tr[1])), mR = Math.max(0, w - Math.max(tr[0], br[0])), mB = Math.max(0, h - Math.max(bl[1], br[1]));
    var pc = [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]].map(function (p) { return apply(fwd, p[0], p[1]); });
    var ox0 = Math.max(Math.min.apply(null, pc.map(function (p) { return p[0]; })), rx0 - mL * 1.15), oy0 = Math.max(Math.min.apply(null, pc.map(function (p) { return p[1]; })), ry0 - mT * 1.15);
    var ox1 = Math.min(Math.max.apply(null, pc.map(function (p) { return p[0]; })), rx0 + RW + mR * 1.15), oy1 = Math.min(Math.max.apply(null, pc.map(function (p) { return p[1]; })), ry0 + RH + mB * 1.15);
    ox0 = Math.floor(ox0); oy0 = Math.floor(oy0);
    var W = Math.max(1, Math.ceil(ox1) - ox0), Ht = Math.max(1, Math.ceil(oy1) - oy0);
    if (W * Ht > w * h * 2.5) return keep("GEOMETRY_INVALID", { angle: round2(angle) });
    // ánh xạ ngược + nội suy song tuyến; ngoài ảnh nguồn = trắng
    var out = new Uint8Array(W * Ht);
    for (var Y = 0; Y < Ht; Y++) for (var X = 0; X < W; X++) {
      var s = apply(inv, X + ox0, Y + oy0), sx = s[0], sy = s[1], v = 255;
      if (sx >= 0 && sy >= 0 && sx <= w - 1 && sy <= h - 1) {
        v = cubic(g, w, h, sx, sy);
      }
      out[Y * W + X] = v < 0 ? 0 : v > 255 ? 255 : Math.round(v);
    }
    return { g: out, w: W, h: Ht, applied: true, status: "RECTIFIED", angle: round2(angle), perspective: perspective,
      corners: quad.map(function (p) { return [round2(p[0]), round2(p[1])]; }), matrix: inv.map(function (x) { return +x.toPrecision(10); }), offset: [ox0, oy0] };
  }

  var api = { rectify: rectify, homography: homography };
  if (NODE) module.exports = api;
  else { root.HAKCore = root.HAKCore || {}; root.HAKCore.rectify = api; }
})(typeof window !== "undefined" ? window : this);
