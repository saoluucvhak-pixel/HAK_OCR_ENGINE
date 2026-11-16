"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("fs"), os = require("os"), path = require("path");
const S = require("../fixtures/synth-digits.js"), F = require("../../core/ocr-learning/features.js");
const { createStore } = require("../../main/ocr-library.js");
const bb = (a, b, c, d) => ({ x0: a, y0: b, x1: c, y1: d });
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "ocrlib-"));
function img(label, seed) { const r = S.render(label, S.prng(seed)); return r; }
function P(label, seed, over) { const im = img(label, seed); return Object.assign({ raw: im.g, clean: im.g, w: im.w, h: im.h, cellType: "digit", docId: "DOC-1", page: 1, bbox: bb(10, 10, 40, 60), employeeId: "NV1", ky: "2026-09", before: "", after: label, ocrValue: "", user: "u1", mode: "so" }, over || {}); }

test("U-OCRL-01 đặc trưng: cùng nhãn giống nhau hơn khác nhãn; ô trống bị nhận ra", () => {
  const a = F.extract(img("1", 1).g, 48, 64), b = F.extract(img("1", 2).g, 48, 64), c = F.extract(img("8", 3).g, 48, 64);
  assert.equal(a.vec.length, F.DIM);
  assert.ok(F.similarity(a.vec, b.vec) > F.similarity(a.vec, c.vec));
  assert.equal(F.extract(new Uint8Array(48 * 64).fill(240), 48, 64).blank, true);
});

test("U-OCRL-02 sửa 1→7→1: giữ lịch sử, chỉ mẫu nhãn cuối còn hiệu lực", () => {
  const st = createStore(tmp());
  st.record(P("1", 1, { before: "", after: "1" }));
  st.record(P("7", 2, { before: "1", after: "7" }));
  st.record(P("1", 3, { before: "7", after: "1" }));
  const all = st.lib.list();
  assert.equal(all.length, 3);
  assert.equal(all.filter((s) => s.status === "PENDING_APPROVAL").length, 1);
  assert.equal(all.filter((s) => s.status === "SUPERSEDED").length, 2);
  assert.equal(st.lib.edits().length, 3);
});

test("U-OCRL-03 duyệt bảng: PENDING→VERIFIED; ký hiệu chưa rõ loại nhãn (UNKNOWN) không tự học", () => {
  const st = createStore(tmp());
  st.record(P("5", 1));
  st.record(P("x", 2, { after: "X", mode: "mark", bbox: bb(60, 10, 90, 60) }));
  const r = st.approve({ docId: "DOC-1", user: "u2" });
  assert.equal(r.verified, 1); assert.equal(r.skippedUnknownKind, 1);
  assert.equal(st.lib.list({ status: "VERIFIED" }).length, 1);
});

test("U-OCRL-04 không có ảnh nguồn: chỉ ghi sự kiện sửa, không tạo mẫu; không đổi giá trị: không ghi gì", () => {
  const st = createStore(tmp());
  const p = P("3", 1); delete p.raw; delete p.clean;
  st.record(p); assert.equal(st.lib.size(), 0); assert.equal(st.lib.edits().length, 1);
  st.record(P("3", 1, { before: "3", after: "3" })); assert.equal(st.lib.edits().length, 1);
});

test("U-OCRL-05 ảnh trùng byte không lưu thêm; tải lại từ đĩa giữ nguyên trạng thái", () => {
  const dir = tmp(), st = createStore(dir);
  st.record(P("2", 5, { bbox: bb(1, 1, 2, 2) })); st.record(P("2", 5, { bbox: bb(3, 3, 4, 4) }));
  assert.equal(st.lib.size(), 1);
  st.approve({ docId: "DOC-1" });
  const st2 = createStore(dir); st2.load();
  assert.equal(st2.lib.size(), 1); assert.equal(st2.lib.list()[0].status, "VERIFIED");
  assert.deepEqual(st2.verify().ok, true);
});

test("U-OCRL-06 dòng nhật ký cuối bị cắt dở được bỏ qua, phần còn lại vẫn nạp", () => {
  const dir = tmp(), st = createStore(dir);
  st.record(P("4", 1)); fs.appendFileSync(path.join(dir, "library.jsonl"), '{"t":"sample","id":"SMP-bad');
  const st2 = createStore(dir); st2.load();
  assert.equal(st2.lib.size(), 1); assert.equal(st2.corrupt(), 1);
});

test("U-OCRL-07 ghi thất bại thì trạng thái bộ nhớ không đổi (không báo đã học)", () => {
  const dir = tmp(), st = createStore(dir); st.load();
  fs.writeFileSync(path.join(dir, "images"), "chặn"); // images là file → mkdir thất bại
  assert.throws(() => st.record(P("6", 1)));
  assert.equal(st.lib.size(), 0);
});

test("U-OCRL-08 xung đột: mẫu mới cùng hình nhưng khác nhãn so với mẫu đã VERIFIED → CONFLICT", () => {
  const st = createStore(tmp());
  st.record(P("7", 1, { docId: "A", bbox: bb(0, 0, 1, 1) })); st.approve({ docId: "A" });
  st.record(P("7", 1, { docId: "B", bbox: bb(5, 5, 6, 6), after: "1" })); // cùng ảnh gán nhãn khác
  const r = st.approve({ docId: "B" });
  assert.equal(r.conflict, 1);
  assert.equal(st.lib.list({ status: "CONFLICT" }).length, 1);
});

test("U-OCRL-09 undoCell hủy sửa gần nhất của ô", () => {
  const st = createStore(tmp());
  st.record(P("9", 1)); st.undoCell(Object.assign({}, st.lib.list()[0]).cellKey, "u1");
  assert.equal(st.lib.list({ status: "PENDING_APPROVAL" }).length, 0);
});

test("U-OCRL-10 tra cứu: không bao giờ AUTO_ACCEPT sai trên dữ liệu tổng hợp; mẫu lạ → UNRECOGNIZED/SUGGESTED", () => {
  const st = createStore(tmp()), rng = S.prng(11); let n = 0;
  "0123456789".split("").forEach((l) => { for (let i = 0; i < 8; i++) { const im = S.render(l, rng); st.record({ raw: im.g, clean: im.g, w: im.w, h: im.h, cellType: "digit", docId: "T", page: 1, bbox: bb(n, n, n + 1, n + 1), after: l, before: "", mode: "so" }); n++; } });
  st.approve({ docId: "T" });
  const items = [], truth = [];
  "0123456789".split("").forEach((l) => { for (let i = 0; i < 15; i++) { const im = S.render(l, rng); items.push({ clean: im.g, w: im.w, h: im.h }); truth.push(l); } });
  const res = st.lookup(items);
  let autoWrong = 0, auto = 0;
  res.forEach((r, i) => { if (r.status === "AUTO_ACCEPT") { auto++; if (r.label !== truth[i]) autoWrong++; } });
  assert.equal(autoWrong, 0); assert.ok(auto > 20, "auto=" + auto);
  const blank = st.lookup([{ clean: new Uint8Array(48 * 64).fill(240), w: 48, h: 64 }])[0];
  assert.equal(blank.status, "UNRECOGNIZED");
});

test("U-OCRL-11 verify phát hiện ảnh mẫu bị mất/sửa", () => {
  const dir = tmp(), st = createStore(dir); st.record(P("8", 1));
  const f = st.files().find((x) => x.rel.endsWith(".png")); fs.writeFileSync(f.abs, "hỏng");
  const v = createStore(dir).verify(); assert.equal(v.ok, false); assert.equal(v.bad.length, 1);
});

test("U-OCRL-12 dịch vụ: sửa ô → gọi ghi mẫu kèm ảnh+bbox; không đổi → bỏ qua; ghi lỗi → xếp hàng và thử lại", async () => {
  const SV = require("../../core/ocr-learning/service.js"), calls = []; let fail = true;
  const api = { record: async (p) => { calls.push(p); return fail ? { ok: false, error: "đĩa đầy" } : { ok: true, sampleId: "S1" }; }, approve: async (q) => ({ ok: true, verified: 2, conflict: 0, skippedUnknownKind: 0, skippedLayout: 0, q }) };
  const sv = SV.createService({ api, user: () => "kt1" });
  const W = 100, H = 80, g = new Uint8Array(W * H).fill(240); for (let y = 20; y < 50; y++) g[y * W + 30] = 20;
  const res = { g, clean: g, w: W, h: H, scale: 1 }, cell = { x0: 20, y0: 10, x1: 60, y1: 60, bb: { x0: 25, y0: 15, x1: 45, y1: 55 }, conf: 70 };
  const pg = { docId: "DOC-1", trang: 3, mode: "so", ky: "2026-09", rot: 0 };
  assert.equal((await sv.onEdit({ res, cell, pg, ma: "NV1", before: "1", after: " 1 " })).skipped, true);
  const r = await sv.onEdit({ res, cell, pg, ma: "NV1", before: "1", after: "7", ocrValue: "1" });
  assert.equal(r.ok, false); assert.equal(sv.pending(), 1);
  assert.equal(calls[0].page, 3); assert.equal(calls[0].user, "kt1"); assert.equal(calls[0].after, "7"); assert.ok(calls[0].raw.length === calls[0].w * calls[0].h);
  fail = false; const f = await sv.flush(); assert.equal(f.sent, 1); assert.equal(sv.pending(), 0);
  const a = await sv.approveCells([{ key: "DOC-1|3|20|10|60|60|0", value: "7" }], "B1"); assert.equal(a.verified, 2);
});

// [U-OCRL-13] kiểm thử tích hợp với Full Backup / kho chứng từ / liên kết chấm công của app lương — giữ ở LUONG_HAK (LuongHAK_Offline/tests), không chuyển sang thư viện.

test("U-OCRL-14 luật nghiệp vụ OCR: ngày ngoài tháng, trùng NV, mã lạ, ô giờ không bị giới hạn công", () => {
  const R = require("../../core/ocr-learning/rules.js");
  const page = { ky: "2026-02", mode: "so", days: [1, 28, 30], lines: [{ ma: "NV1", kind: "Công", vals: { 1: "1", 28: "5" } }, { ma: "NV1", kind: "Công", vals: { 1: "x" } }, { ma: "ZZ", kind: "Công", vals: {} }] };
  const r = R.check(page, { maSet: { NV1: 1 } }), codes = r.issues.map((i) => i.code);
  assert.ok(codes.includes("NGAY_NGOAI_KY") && codes.includes("TRUNG_NV") && codes.includes("MA_NV_LA") && codes.includes("O_KHONG_PHAI_SO") && codes.includes("CONG_NGOAI_KHOANG"));
  assert.equal(r.layoutSuspect, true);
  const g = R.check({ ky: "2026-02", mode: "ca", days: [1], lines: [{ ma: "NV1", kind: "Công", vals: { 1: "8" } }] }, { maSet: { NV1: 1 } });
  assert.equal(g.issues.length, 0); assert.equal(R.daysIn("2024-02"), 29);
});

function gridRes(nc, nr, o) { // bảng tổng hợp nc cột × nr dòng; o: {x0,y0,cw,ch,jx}
  o = Object.assign({ x0: 100, y0: 200, cw: 40, ch: 30, jx: 0 }, o || {}); const cells = [];
  for (let r = 0; r < nr; r++) for (let c = 0; c < nc; c++) { const x0 = o.x0 + c * o.cw + (c % 2 ? o.jx : 0), y0 = o.y0 + r * o.ch; cells.push({ x0, y0, x1: x0 + o.cw, y1: y0 + o.ch, cx: x0 + o.cw / 2, cy: y0 + o.ch / 2 }); }
  return { cells, box: { x0: o.x0, y0: o.y0, x1: o.x0 + nc * o.cw, y1: o.y0 + nr * o.ch }, w: 2000, h: 2800 };
}
test("U-OCRL-15 bố cục: cùng khung ở vị trí/độ phân giải khác vẫn khớp; số dòng khác vẫn khớp; số cột khác → MISMATCH", () => {
  const LY = require("../../core/ocr-learning/layout.js"), a = LY.signature(gridRes(33, 10));
  const lays = [{ id: "L1", name: "Chấm công kho", sig: a }];
  assert.equal(LY.match(LY.signature(gridRes(33, 10, { x0: 340, y0: 90, cw: 80, ch: 60 })), lays).status, "MATCH"); // phóng 2× và dịch chỗ
  assert.equal(LY.match(LY.signature(gridRes(33, 14)), lays).status, "MATCH");
  assert.equal(LY.match(LY.signature(gridRes(20, 10)), lays).status, "MISMATCH");
  assert.equal(LY.match(LY.signature(gridRes(33, 10)), []).status, "NEW");
  assert.equal(LY.match(null, lays).status, "MISMATCH");
});
// [U-OCRL-16] kiểm thử tích hợp với Full Backup / kho chứng từ / liên kết chấm công của app lương — giữ ở LUONG_HAK (LuongHAK_Offline/tests), không chuyển sang thư viện.

test("U-OCRL-17 lớp chữ PDF: bảng chấm công dạng chữ được dựng không cần OCR; PDF scan (ít chữ) → không dùng", () => {
  const PT = require("../../core/ocr-learning/pdf-text.js"), items = [];
  const put = (str, x, y, w) => items.push({ str, x0: x, x1: x + (w || 30), y0: y, y1: y + 14 });
  put("Bảng chấm công tháng 11/2026", 20, 40, 300); put("Họ và tên", 20, 100, 120); for (let d = 1; d <= 10; d++) put(String(d), 150 + d * 40, 100); put("Tổng công", 150 + 11 * 40, 100, 70);
  [["Nguyễn Văn An", 1], ["Trần Thị Bình", 0.5]].forEach(([n, v], r) => { const y = 130 + r * 30; put(n, 20, y, 120); let s = 0; for (let d = 1; d <= 10; d++) { put(String(v).replace(".", ","), 150 + d * 40, y); s += v; } put(String(s).replace(".", ","), 150 + 11 * 40, y, 70); });
  const r = PT.analyze(items, { w: 1000, h: 800 });
  assert.equal(r.usable, true, r.reason); assert.ok(r.table.lines.length >= 2);
  const l = r.table.lines.find((x) => /An/.test(x.name)); assert.ok(l, JSON.stringify(r.table.lines.map((x) => x.name)));
  assert.equal(l.values[3], 1); const b = r.table.lines.find((x) => /Bình/.test(x.name)); assert.equal(b.values[3], 0.5);
  assert.equal(r.period, "2026-11"); assert.ok(r.title.some((t) => /tháng/.test(t)));
  assert.equal(PT.analyze(items.slice(0, 5), { w: 1000, h: 800 }).usable, false);
  assert.equal(PT.analyze([], {}).usable, false);
  // gộp mảnh "0" "," "5" cùng dòng
  const m = PT.mergeRuns([{ str: "0", x0: 10, x1: 16, y0: 0, y1: 14 }, { str: ",", x0: 16.5, x1: 19, y0: 0, y1: 14 }, { str: "5", x0: 19.5, x1: 26, y0: 0, y1: 14 }]);
  assert.equal(m.length, 1); assert.equal(m[0].str, "0,5");
});

test("U-OCRL-18 kịch bản nghiệp vụ: 0,5→0,6 (nhãn thập phân), ô trống→1 (có nét), xóa giá trị, X là ký hiệu chưa rõ loại, ảnh gần trùng không phình thư viện", () => {
  const st = createStore(tmp()), im = (l, sd) => S.render(l, S.prng(sd)), mk = (l, sd, o) => { const i = im(l, sd); return Object.assign({ raw: i.g, clean: i.g, w: i.w, h: i.h, cellType: "digit", docId: "D", page: 1, bbox: bb(1, 1, 2, 2), mode: "so" }, o); };
  st.record(mk("5", 1, { before: "0,5", after: "0,6", ocrValue: "0,5" }));
  assert.equal(st.lib.list()[0].label, "0.6"); assert.equal(st.lib.list()[0].ocrValue, "0.5"); assert.equal(st.lib.edits()[0].from, "0.5");
  st.record(mk("1", 2, { before: "", after: "1", bbox: bb(9, 9, 10, 10) })); assert.equal(st.lib.list().length, 2); // ô trống → 1
  st.record(mk("1", 2, { before: "1", after: "", bbox: bb(9, 9, 10, 10) })); // xóa giá trị: ghi sự kiện, KHÔNG tạo mẫu
  assert.equal(st.lib.list().length, 2); assert.equal(st.lib.edits().length, 3); assert.equal(st.lib.list()[1].status, "SUPERSEDED"); // V8: mẫu của ô đã xóa không còn hiệu lực
  st.record(mk("x", 3, { before: "", after: "X", mode: "mark", cellType: "mark", bbox: bb(20, 20, 21, 21) }));
  const x = st.lib.list().find((s) => s.label === "X"); assert.equal(x.labelKind, "UNKNOWN");
  st.lib.cfg.nearDupSim = 0.9; // hai ảnh "1" khác hạt giống nhưng rất giống nhau → gần trùng
  st.record(mk("1", 4, { before: "", after: "1", bbox: bb(30, 30, 31, 31) })); const n0 = st.lib.size(); st.record(mk("1", 6, { before: "", after: "1", bbox: bb(40, 40, 41, 41) })); assert.equal(st.lib.size(), n0);
});
