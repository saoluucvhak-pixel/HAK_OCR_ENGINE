"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const NM = require("../../core/ocr-learning/name-memory.js");
const cat = [{ ma: "A1", ten: "Nguyễn Văn An" }, { ma: "B2", ten: "Trần Thị Bé" }, { ma: "C3", ten: "Lê Văn Cường" }, { ma: "C4", ten: "Lê Văn Cường" }];
const ev = (raw, ma, doc, cell) => ({ raw, ma, docId: doc, page: 1, cellKey: cell || "k1", user: "u" });
test("U-NAME-01: ghi sự kiện xác nhận; trùng (chứng từ|trang|ô|mã) không ghi lại; thiếu mã/tên thì bỏ qua", () => {
  const L = [];
  assert.ok(NM.record(L, ev("Nguyen Van An", "A1", "D1")));
  assert.equal(NM.record(L, ev("Nguyen Van An", "A1", "D1")), null);
  assert.equal(NM.record(L, ev("", "A1", "D1", "k2")), null); assert.equal(NM.record(L, ev("x", "", "D1", "k3")), null);
  assert.equal(L.length, 1); assert.equal(L[0].rawFold, "nguyen van an");
});
test("U-NAME-02: gợi ý không dấu; chỉ chọn sẵn khi đã xác nhận trên ≥ 2 chứng từ", () => {
  const L = []; NM.record(L, ev("Nguyễn V. An", "A1", "D1"));
  let s = NM.suggest(L, "nguyen v an", cat); assert.equal(s.ma, "A1"); assert.equal(s.preselect, false);
  NM.record(L, ev("Nguyễn V. An", "A1", "D2")); s = NM.suggest(L, "NGUYEN V. AN", cat); assert.equal(s.preselect, true); assert.equal(s.ambiguous, false);
});
test("U-NAME-03: trùng họ tên trong danh mục → không tự chọn dù đã xác nhận (không nhầm người trùng tên)", () => {
  const L = []; NM.record(L, ev("Le V Cuong", "C3", "D1")); NM.record(L, ev("Le V Cuong", "C3", "D2"));
  const s = NM.suggest(L, "Le V Cuong", cat); assert.equal(s.ambiguous, true); assert.equal(s.preselect, false); assert.match(s.why, /Trùng họ tên/);
  assert.deepEqual(NM.sameNameGroups(cat), [["C3", "C4"]]);
});
test("U-NAME-04: cùng chuỗi từng xác nhận cho 2 người khác nhau → xung đột, không gợi ý chọn", () => {
  const L = []; NM.record(L, ev("An", "A1", "D1")); NM.record(L, ev("An", "B2", "D2"));
  const s = NM.suggest(L, "An", cat); assert.equal(s.conflict, true); assert.equal(s.ma, "");
});
test("U-NAME-05: Mã NV không còn trong danh mục → bỏ gợi ý; hoàn tác chỉ đánh dấu, không xóa lịch sử", () => {
  const L = []; NM.record(L, ev("Bé", "ZZ", "D1")); assert.equal(NM.suggest(L, "Bé", cat), null);
  NM.record(L, ev("Bé", "B2", "D1", "k9")); assert.ok(NM.suggest(L, "Be", cat));
  assert.equal(NM.undo(L, "D1", "k9"), 1); assert.equal(L.length, 2); assert.equal(NM.suggest(L, "Be", cat), null);
});
