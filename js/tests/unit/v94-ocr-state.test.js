// V9.4 — trạng thái lưu mẫu OCR hiển thị cho người dùng (core/ocr-learning/service.js)
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../../core/ocr-learning/service.js");

const mk = (rec, spool) => L.createService({ api: Object.assign({ record: rec }, spool || {}), user: () => "u" });
const cell = { x0: 1, y0: 1, x1: 9, y1: 9, conf: 40 };

test("U-OCRS-01: ghi thành công → saved; thiếu ảnh nguồn → missing; sửa về cùng giá trị → bỏ qua", async () => {
  const s = mk((p) => Promise.resolve({ ok: true, sampleId: "S1", missingSource: !p.bbox }));
  await s.onEdit({ cell, ref: "A|01", before: "1", after: "7", pg: {} });
  await s.onEdit({ cell: null, ref: "B|02", before: "", after: "1", pg: {} });
  const sk = await s.onEdit({ cell, ref: "A|03", before: "1", after: "1", pg: {} });
  assert.equal(sk.skipped, true);
  assert.equal(s.stateOf("A|01").state, "saved"); assert.equal(s.stateOf("A|01").sampleId, "S1");
  assert.equal(s.stateOf("B|02").state, "missing");
  assert.equal(s.stateOf("A|03"), null);
  assert.deepEqual(s.stats(), { saved: 1, missing: 1, queued: 0, error: 0 });
});
test("U-OCRS-02: ghi lỗi → queued (giữ để thử lại), ô kế tiếp ghi được thì hàng đợi vẫn còn; không ném lỗi", async () => {
  let fail = true;
  const s = mk(() => (fail ? Promise.reject(new Error("đĩa đầy")) : Promise.resolve({ ok: true, sampleId: "S2" })), { spoolPut: () => Promise.resolve({ ok: true }), spoolRemove() {} });
  const r = await s.onEdit({ cell, ref: "A|01", before: "1", after: "7", pg: {} });
  assert.equal(r.queued, true); assert.equal(s.stateOf("A|01").state, "queued"); assert.equal(s.pending(), 1);
  fail = false;
  const f = await s.flush(); assert.equal(f.sent, 1); assert.equal(s.pending(), 0);
});
test("U-OCRS-03: xóa trắng (7 → rỗng) và nhập mới (rỗng → 1) đều được ghi sự kiện; cùng ô sửa nhiều lần giữ trạng thái mới nhất", async () => {
  const seen = []; const s = mk((p) => { seen.push([p.before, p.after]); return Promise.resolve({ ok: true, sampleId: "S" + seen.length }); });
  await s.onEdit({ cell, ref: "A|01", before: "7", after: "", pg: {} });
  await s.onEdit({ cell, ref: "A|01", before: "", after: "1", pg: {} });
  assert.deepEqual(seen, [["7", ""], ["", "1"]]);
  assert.equal(s.events().length, 2); assert.equal(s.stats().saved, 1);
});
