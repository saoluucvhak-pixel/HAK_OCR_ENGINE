"use strict";
// V8 P0-2: xóa / sửa lại / hoàn tác ô OCR — mẫu cũ không được "sống" sau khi ô đã đổi
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("fs"), os = require("os"), path = require("path");
const S = require("../fixtures/synth-digits.js");
const { createStore } = require("../../main/ocr-library.js");
const bb = (a, b, c, d) => ({ x0: a, y0: b, x1: c, y1: d });
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "ocrlib8-"));
function P(label, seed, over) { const im = S.render(label, S.prng(seed)); return Object.assign({ raw: im.g, clean: im.g, w: im.w, h: im.h, cellType: "digit", docId: "D1", page: 1, bbox: bb(10, 10, 40, 60), employeeId: "NV1", ky: "2026-09", before: "", after: label, user: "u" }, over || {}); }
const key = (st) => st.lib.edits()[0].cellKey;
const act = (st) => st.lib.list().filter((s) => s.status === "PENDING_APPROVAL" || s.status === "VERIFIED");

test("U-OCR8-01 A: 1→7→xóa trống: giữ lịch sử, mẫu '7' không còn hiệu lực, không có mẫu nhãn trống", () => {
  const st = createStore(tmp());
  st.record(P("1", 1)); st.record(P("7", 2, { before: "1", after: "7" }));
  const r = st.record(P("7", 3, { before: "7", after: "", raw: null, clean: null }));
  assert.equal(r.sampleId, null);
  assert.equal(act(st).length, 0, "không mẫu nào còn hiệu lực");
  assert.equal(st.lib.list().filter((s) => s.label === "").length, 0, "không tạo ảnh nhãn rỗng");
  assert.equal(st.lib.edits().length, 3);
  assert.equal(st.lib.cellSample(key(st)), null);
  assert.ok(st.lib.list().every((s) => s.status === "SUPERSEDED"));
});

test("U-OCR8-02 B: 1→7→1 chỉ mẫu cuối hiệu lực; ô được gán đúng mẫu cuối", () => {
  const st = createStore(tmp());
  st.record(P("1", 1)); st.record(P("7", 2, { before: "1", after: "7" })); const r = st.record(P("1", 3, { before: "7", after: "1" }));
  assert.equal(act(st).length, 1); assert.equal(st.lib.cellSample(key(st)), r.sampleId);
});

test("U-OCR8-03 C: 0,5→0,6→Undo: ô về 0,5, mẫu 0,5 hiệu lực lại, sự kiện UNDO được ghi", () => {
  const st = createStore(tmp());
  const a = st.record(P("5", 1, { before: "", after: "0,5" })), b = st.record(P("6", 2, { before: "0,5", after: "0,6" }));
  const u = st.undoCell(key(st), "u");
  assert.equal(u.value, "0.5"); // nhãn đã chuẩn hóa dấu phẩy → chấm
  assert.equal(st.lib.cellSample(key(st)), a.sampleId);
  assert.equal(st.lib.get(a.sampleId).status, "PENDING_APPROVAL");
  assert.equal(st.lib.get(b.sampleId).status, "REJECTED");
  assert.equal(st.lib.edits().filter((e) => e.kind === "UNDO").length, 1);
});

test("U-OCR8-04 D: khởi động lại nạp từ đĩa → lịch sử, trạng thái, gán ô giống hệt", () => {
  const dir = tmp(), st = createStore(dir);
  st.record(P("5", 1, { after: "0,5" })); st.record(P("6", 2, { before: "0,5", after: "0,6" })); st.undoCell(key(st), "u");
  st.record(P("1", 3, { docId: "D2", after: "1" })); st.record(P("1", 3, { docId: "D2", before: "1", after: "", raw: null, clean: null }));
  const st2 = createStore(dir); st2.load();
  assert.deepEqual(st2.lib.list().map((s) => s.status), st.lib.list().map((s) => s.status));
  assert.equal(st2.lib.edits().length, st.lib.edits().length);
  assert.equal(st2.lib.cellSample(key(st2)), st.lib.cellSample(key(st)));
});

test("U-OCR8-05 sửa khi thiếu ảnh nguồn vẫn gỡ mẫu cũ và đánh dấu MISSING_SOURCE_IMAGE", () => {
  const st = createStore(tmp());
  st.record(P("1", 1)); const r = st.record(P("7", 2, { before: "1", after: "7", raw: null, clean: null }));
  assert.ok(r.missingSource); assert.equal(act(st).length, 0);
  assert.deepEqual(st.lib.edits()[1].flags, ["MISSING_SOURCE_IMAGE"]);
});

test("U-OCR8-06 ảnh dùng chung cho 2 ô: xóa 1 ô không vô hiệu mẫu của ô còn lại", () => {
  const st = createStore(tmp());
  const a = st.record(P("7", 5, { bbox: bb(0, 0, 30, 50) })), b = st.record(P("7", 5, { bbox: bb(100, 0, 130, 50), employeeId: "NV2" }));
  assert.equal(a.sampleId, b.sampleId);
  const k1 = st.lib.edits()[0].cellKey;
  st.record(P("7", 5, { bbox: bb(0, 0, 30, 50), before: "7", after: "", raw: null, clean: null }));
  assert.equal(st.lib.get(a.sampleId).status, "PENDING_APPROVAL");
  assert.equal(st.lib.cellSample(k1), null);
  st.record(P("7", 5, { bbox: bb(100, 0, 130, 50), before: "7", after: "", raw: null, clean: null }));
  assert.equal(st.lib.get(a.sampleId).status, "SUPERSEDED");
});

test("U-OCR8-07 sửa lặp 100 lần cùng ô: đúng 1 mẫu hiệu lực, 100 sự kiện", () => {
  const st = createStore(tmp()); let before = "";
  for (let i = 0; i < 100; i++) { const l = String(i % 2 ? 7 : 1); st.record(P(l, 10 + i, { before, after: l })); before = l; }
  assert.equal(act(st).length, 1); assert.equal(st.lib.edits().length, 100);
});

// ---- V8 P0-4: chỉ duyệt mẫu của ô thực sự đã nhập ----
test("U-OCR8-08 trang 30 dòng: 25 dòng nhập được + 5 dòng lỗi → chỉ 25 mẫu VERIFIED, 5 mẫu còn PENDING", () => {
  const st = createStore(tmp()), keys = [];
  for (let i = 0; i < 30; i++) { const l = String(i % 9 + 1); st.record(P(l, 100 + i, { bbox: bb(i * 50, 0, i * 50 + 40, 60), employeeId: "NV" + i })); }
  st.lib.edits().forEach((e, i) => { if (i < 25) keys.push({ key: e.cellKey, value: st.lib.get(e.sampleId).label }); });
  const r = st.approve({ cellKeys: keys, batchId: "IMP-1", user: "u" });
  assert.equal(r.verified + r.conflict, 25);
  assert.equal(st.lib.list({ status: "PENDING_APPROVAL" }).length, 5);
});

test("U-OCR8-09 giá trị đã nhập khác nhãn mẫu → không duyệt; ô không có mẫu gán → bỏ qua", () => {
  const st = createStore(tmp()); st.record(P("7", 1));
  const k = st.lib.edits()[0].cellKey;
  const r = st.approve({ cellKeys: [{ key: k, value: "1" }, { key: "không|có|ô", value: "3" }] });
  assert.equal(r.verified, 0); assert.equal(r.skippedMismatch, 1); assert.equal(r.skippedNotAssigned, 1);
  assert.equal(st.lib.list({ status: "PENDING_APPROVAL" }).length, 1);
});

test("U-OCR8-10 nhãn UNKNOWN / nghi lỗi bố cục không được duyệt dù ô đã nhập", () => {
  const st = createStore(tmp());
  st.record(P("x", 1, { mode: "mark", cellType: "mark", after: "X", bbox: bb(0, 0, 9, 9) }));
  st.record(P("3", 2, { layoutSuspect: true, bbox: bb(20, 0, 29, 9) }));
  const keys = st.lib.edits().map((e) => ({ key: e.cellKey }));
  const r = st.approve({ cellKeys: keys });
  assert.equal(r.verified, 0); assert.equal(r.skippedUnknownKind, 1); assert.equal(r.skippedLayout, 1);
});

// ---- V8 P0-3: sự kiện cho mọi ô sửa, hàng đợi bền, idempotent ----
test("U-OCR8-11 TransactionID: gửi lại cùng một lần sửa không tạo sự kiện/mẫu trùng", () => {
  const st = createStore(tmp()); const p = P("7", 1, { txId: "TXabc123" });
  st.record(p); st.record(p); st.record(p);
  assert.equal(st.lib.edits().length, 1); assert.equal(st.lib.list().length, 1);
  const st2 = createStore(st.root); st2.load(); st2.record(p); // sau khởi động lại vẫn nhận ra
  assert.equal(st2.lib.edits().length, 1);
});

test("U-OCR8-12 hàng đợi bền: ghi lỗi → spool đĩa → 'khởi động lại' nạp lại → ghi được, không trùng, spool sạch", async () => {
  const SV = require("../../core/ocr-learning/service.js");
  const root = tmp(), spoolDir = tmp(), store = createStore(root, { spoolDir });
  let down = true;
  const api = {
    record: async (p) => { if (down) return { ok: false, error: "đĩa lỗi" }; const r = store.recordSpooled(p); return { ok: true, sampleId: r.sampleId }; },
    spoolPut: async (p) => { store.spoolPut(p); return { ok: true }; }, spoolList: async () => ({ ok: true, items: store.spoolList() }), spoolRemove: async (t) => { store.spoolRemove(t); return { ok: true }; },
  };
  const sv = SV.createService({ api, user: () => "u" });
  const W = 60, H = 80, g = new Uint8Array(W * H).fill(240); for (let y = 15; y < 65; y++) g[y * W + 30] = 10;
  const res = { g, clean: g, w: W, h: H, scale: 1 }, cell = { x0: 5, y0: 5, x1: 55, y1: 75, conf: 50 }, pg = { docId: "D", trang: 1, mode: "so" };
  const r = await sv.onEdit({ res, cell, pg, ma: "NV1", before: "1", after: "7" });
  assert.equal(r.queued, true); assert.equal(r.durable, true); assert.equal(sv.pending(), 1);
  assert.equal(store.spoolList().length, 1);
  const sv2 = SV.createService({ api, user: () => "u" }); // mô phỏng mở lại ứng dụng
  assert.equal((await sv2.restoreQueue()).restored, 1); assert.equal(sv2.pending(), 1);
  down = false;
  const f = await sv2.flush(); assert.equal(f.sent, 1); assert.equal(sv2.pending(), 0);
  assert.equal(store.spoolList().length, 0); assert.equal(store.lib.edits().length, 1);
  await sv.flush(); // bản cũ trong RAM của phiên trước thử lại → trùng TransactionID, không tạo thêm
  assert.equal(store.lib.edits().length, 1); assert.equal(store.lib.list().length, 1);
});

test("U-OCR8-13 ô sửa không có ô (cell) / không có ảnh: vẫn ghi sự kiện + cờ MISSING_SOURCE_IMAGE, không mẫu giả", async () => {
  const SV = require("../../core/ocr-learning/service.js"), store = createStore(tmp());
  const api = { record: async (p) => { const r = store.record(p); return { ok: true, sampleId: r.sampleId, missingSource: r.missingSource }; } };
  const sv = SV.createService({ api, user: () => "u" });
  const r = await sv.onEdit({ res: null, cell: null, ref: "NV1|05", pg: { docId: "D", trang: 2 }, ma: "NV1", before: "1", after: "7" });
  assert.equal(r.ok, true); assert.equal(r.missingSource, true);
  assert.equal(store.lib.list().length, 0);
  const e = store.lib.edits()[0]; assert.deepEqual(e.flags, ["MISSING_SOURCE_IMAGE"]); assert.match(e.cellKey, /\|ref\|NV1\|05$/);
});

// ---- V8 P0-7: liên kết ô chấm công ↔ chứng từ gốc ----
// [U-OCR8-14] kiểm thử tích hợp với Full Backup / kho chứng từ / liên kết chấm công của app lương — giữ ở LUONG_HAK (LuongHAK_Offline/tests), không chuyển sang thư viện.

test("U-OCR8-15: cặp dễ nhầm 1/7, 3/8, 0/6, 5/6, 0.5/0.6, X/- được nhận diện; cặp khác thì không", () => {
  const L = require("../../core/ocr-learning/library.js").lookalike;
  [["1", "7"], ["3", "8"], ["0", "6"], ["5", "6"], ["0,5", "0.6"], ["0.5", "0.6"], ["X", "-"], ["x", "-"], ["12", "72"]].forEach(([a, b]) => assert.equal(L(a, b), true, a + "/" + b));
  [["1", "2"], ["0.5", "0.5"], ["10", "1"], ["", "1"], ["4", "9"]].forEach(([a, b]) => assert.equal(L(a, b), false, a + "/" + b));
});

test("U-OCR8-16: mẫu '1' đã học nhưng Tesseract đọc '7' → không AUTO_ACCEPT, chỉ SUGGESTED", () => {
  const st = createStore(tmp()), rng = S.prng(5);
  for (let i = 0; i < 6; i++) { const im = S.render("1", rng); st.record({ raw: im.g, clean: im.g, w: im.w, h: im.h, cellType: "digit", docId: "T", page: 1, bbox: bb(i, i, i + 1, i + 1), before: "", after: "1" }); }
  st.approve({ docId: "T" });
  const im = S.render("1", rng);
  const base = st.lookup([{ clean: im.g, w: im.w, h: im.h }])[0];
  const withTess = st.lookup([{ clean: im.g, w: im.w, h: im.h, ocrText: "7", ocrConf: 40 }])[0];
  assert.equal(base.label, "1");
  assert.notEqual(withTess.status, "AUTO_ACCEPT");
});
