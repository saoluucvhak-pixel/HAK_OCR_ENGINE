// ===== CORE / OCR-LEARNING / RULES — kiểm tra nghiệp vụ trên kết quả OCR một trang (V7 GĐ6) =====
// Thuần (không DOM). Mức: ERROR (chặn ghi dòng) | WARN (cảnh báo). Lỗi cấu trúc (STRUCT) → trang nghi lỗi bố cục → KHÔNG học mẫu từ trang đó.
// Ô giờ / số ca (mode ≠ "so") không áp giới hạn của quy tắc công BT.
(function (root) {
  "use strict";
  function daysIn(ky) { var m = /^(\d{4})-(\d{2})$/.exec(String(ky || "")); if (!m) return 0; return new Date(+m[1], +m[2], 0).getDate(); }
  function num(v) { if (v === "" || v == null) return null; var n = Number(String(v).replace(",", ".")); return isFinite(n) ? n : NaN; }
  /** page: { ky, mode, days:[..], lines:[{name, ma, kind, vals:{d:string}, src:{totals}}] }; opts: { maSet:{ma:1}, maxPerDay (mặc định 3), sumOf(line)→number } */
  function check(page, opts) {
    opts = opts || {}; var out = [], dim = daysIn(page.ky), maxDay = opts.maxPerDay == null ? 3 : opts.maxPerDay, so = !page.mode || page.mode === "so";
    function add(level, code, li, d, msg, struct) { out.push({ level: level, code: code, line: li, day: d == null ? null : d, msg: msg, struct: !!struct }); }
    if (!dim) add("ERROR", "KY_SAI", null, null, "Kỳ của trang không hợp lệ (cần dạng YYYY-MM)", true);
    (page.days || []).forEach(function (d) { if (dim && (d < 1 || d > dim)) add("ERROR", "NGAY_NGOAI_KY", null, d, "Cột ngày " + d + " không có trong tháng " + page.ky + " (" + dim + " ngày) — nghi đọc sai bố cục / sai kỳ", true); });
    if (!(page.lines || []).length) add("ERROR", "KHONG_DONG", null, null, "Không có dòng nào", true);
    var seen = {};
    (page.lines || []).forEach(function (L, li) {
      if (!L.kind) return; // dòng bỏ qua
      if (!L.ma) add("WARN", "CHUA_CHON_NV", li, null, "Dòng " + (li + 1) + " chưa chọn nhân viên");
      else {
        if (opts.maSet && !opts.maSet[L.ma]) add("ERROR", "MA_NV_LA", li, null, "Mã NV " + L.ma + " không có trong danh mục");
        var k = L.ma + "|" + L.kind; if (seen[k] != null) add("ERROR", "TRUNG_NV", li, null, "Mã NV " + L.ma + " (" + L.kind + ") trùng với dòng " + (seen[k] + 1)); else seen[k] = li;
      }
      Object.keys(L.vals || {}).forEach(function (d) {
        var n = num(L.vals[d]);
        if (n !== null && isNaN(n)) add("ERROR", "O_KHONG_PHAI_SO", li, +d, "Dòng " + (li + 1) + " ngày " + d + ": \"" + L.vals[d] + "\" không phải số");
        else if (so && n !== null && (n < 0 || n > maxDay)) add("WARN", "CONG_NGOAI_KHOANG", li, +d, "Dòng " + (li + 1) + " ngày " + d + ": " + L.vals[d] + " công ngoài khoảng 0–" + maxDay);
      });
      var tot = L.src && L.src.totals ? Object.keys(L.src.totals).map(function (k2) { return L.src.totals[k2]; }).filter(function (x) { return x != null && !isNaN(x); })[0] : null;
      if (tot != null && opts.sumOf) { var s = opts.sumOf(L); if (Math.abs(s - tot) > 0.01) add("WARN", "LECH_TONG_DONG", li, null, "Dòng " + (li + 1) + ": tổng tính " + s + " ≠ tổng trên giấy " + tot); }
    });
    var struct = out.some(function (x) { return x.struct; });
    return { issues: out, errors: out.filter(function (x) { return x.level === "ERROR"; }).length, warns: out.filter(function (x) { return x.level === "WARN"; }).length, layoutSuspect: struct };
  }
  var API = { check: check, daysIn: daysIn };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else { root.HAKCore = root.HAKCore || {}; root.HAKCore.ocrRules = API; }
})(typeof self !== "undefined" ? self : this);
