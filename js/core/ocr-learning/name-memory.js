// ===== CORE / OCR — NHỚ CÁCH ĐỌC TÊN NHÂN VIÊN (V9) =====
// Tách bạch 4 thứ: (1) chuỗi chữ đọc từ ảnh, (2) chuỗi người dùng xác nhận, (3) EmployeeID (Mã NV) thật, (4) việc ghép đúng người từ DANH MỤC.
// Bộ nhớ chỉ ghi sự kiện "chuỗi X trên giấy đã được xác nhận là Mã NV Y" (kèm chứng từ/trang/ô/kỳ/người xác nhận) — KHÔNG tự coi
// hai người cùng tên là một. Gợi ý chỉ dùng được khi: Mã NV còn trong danh mục, chuỗi này chỉ từng được xác nhận cho MỘT Mã NV,
// và họ tên trong danh mục không trùng với người khác. Trùng tên/xung đột → không gợi ý tự chọn (người dùng chọn theo mã).
(function (root) {
  "use strict";
  function fold(s) { return String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
  function uid() { return "NM" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  /** Ghi sự kiện xác nhận (idempotent theo chứng từ|trang|ô|mã). @returns sự kiện mới | null (bỏ qua/đã có) */
  function record(list, ev) {
    if (!Array.isArray(list) || !ev) return null;
    var raw = String(ev.raw || "").trim(), ma = String(ev.ma || "").trim();
    if (!fold(raw) || !ma) return null;
    var key = [ev.docId || "-", ev.page || 0, ev.cellKey || "", ma].join("|");
    for (var i = 0; i < list.length; i++) if (list[i].key === key && !list[i].huy) return null;
    var e = { id: uid(), key: key, at: ev.at || new Date().toISOString(), user: ev.user || "", raw: raw, rawFold: fold(raw), typed: String(ev.typed == null ? raw : ev.typed).trim(),
      ma: ma, tenDM: ev.tenDM || "", docId: ev.docId || "", page: ev.page || 0, cellKey: ev.cellKey || "", runId: ev.runId || "", ky: ev.ky || "", sua: !!ev.sua };
    list.push(e); return e;
  }
  /** Gợi ý theo bộ nhớ. catalog: [{ma,ten}]. @returns { ma, ten, n, preselect, ambiguous, conflict, why } | null */
  function suggest(list, rawName, catalog) {
    var f = fold(rawName); if (!f || !Array.isArray(list)) return null;
    var byMa = {}; list.forEach(function (e) { if (!e.huy && (e.rawFold === f || fold(e.typed) === f)) { (byMa[e.ma] = byMa[e.ma] || { n: 0, docs: {} }).n++; byMa[e.ma].docs[e.docId || e.id] = 1; } });
    var cat = {}; (catalog || []).forEach(function (c) { cat[c.ma] = c; });
    var mas = Object.keys(byMa).filter(function (m) { return cat[m]; });
    if (!mas.length) return null;
    if (mas.length > 1) return { ma: "", ten: "", n: 0, preselect: false, ambiguous: true, conflict: true, why: "Chuỗi này từng được xác nhận cho " + mas.length + " nhân viên khác nhau — chọn theo mã" };
    var ma = mas[0], c = cat[ma], dup = (catalog || []).filter(function (x) { return x.ma !== ma && fold(x.ten) === fold(c.ten); });
    var docs = Object.keys(byMa[ma].docs).length;
    if (dup.length) return { ma: ma, ten: c.ten, n: byMa[ma].n, preselect: false, ambiguous: true, conflict: false, why: "Trùng họ tên với " + dup.length + " nhân viên khác — không tự chọn, kiểm tra theo mã" };
    return { ma: ma, ten: c.ten, n: byMa[ma].n, preselect: docs >= 2, ambiguous: false, conflict: false, why: "Đã xác nhận " + byMa[ma].n + " lần" + (docs >= 2 ? " trên " + docs + " chứng từ" : "") };
  }
  /** Hai nhân viên trong danh mục cùng họ tên (sau khi bỏ dấu) → không được tự chọn theo tên. */
  function sameNameGroups(catalog) { var g = {}; (catalog || []).forEach(function (c) { var f = fold(c.ten); if (f) (g[f] = g[f] || []).push(c.ma); }); return Object.keys(g).filter(function (k) { return g[k].length > 1; }).map(function (k) { return g[k]; }); }
  /** Hủy các xác nhận của 1 chứng từ/ô (khi người dùng hoàn tác) — đánh dấu, không xóa lịch sử. */
  function undo(list, docId, cellKey) { var n = 0; (list || []).forEach(function (e) { if (!e.huy && e.docId === docId && e.cellKey === cellKey) { e.huy = true; e.huyLuc = new Date().toISOString(); n++; } }); return n; }
  var api = { fold: fold, record: record, suggest: suggest, sameNameGroups: sameNameGroups, undo: undo };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else { root.HAKCore = root.HAKCore || {}; root.HAKCore.ocrNameMemory = api; }
})(typeof self !== "undefined" ? self : this);
