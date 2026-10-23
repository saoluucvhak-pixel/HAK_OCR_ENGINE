"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), path = require("node:path");
const V = require("../../scripts/paddle/vi-charset.cjs");
const DIR = path.join(__dirname, "../../ocr/paddle");
const latin = V.readDict(path.join(DIR, "ppocrv5_latin_dict.txt")), vi = V.readDict(path.join(DIR, "vi_latin_dict.txt"));

test("bảng chữ Việt đủ 178 chữ (17 phụ âm + 12 nguyên âm × 6 thanh = 89, thường + hoa), đều ở dạng dựng sẵn NFC", () => {
  const L = V.vietnameseLetters();
  assert.equal(L.length, 178); assert.equal(new Set(L).size, 178);
  L.forEach((c) => { assert.equal(c.length, 1, JSON.stringify(c)); assert.equal(c.normalize("NFC"), c); });
  ["ạ", "ấ", "ầ", "ẩ", "ẫ", "ậ", "ằ", "ổ", "ỗ", "ữ", "ỵ", "Ỹ", "Đ"].forEach((c) => assert.ok(L.includes(c), c));
});

test("từ điển tiếng Việt: giữ NGUYÊN 836 dòng latin (cùng thứ tự = cùng chỉ số lớp của model gốc), chỉ thêm vào cuối", () => {
  assert.equal(latin.length, 836);
  assert.deepEqual(vi.slice(0, latin.length), latin);
  assert.equal(vi.length, 926);
  const added = vi.slice(latin.length);
  assert.equal(new Set(added).size, added.length);
  added.forEach((c) => assert.ok(!latin.includes(c), "đã có sẵn: " + c));
  assert.deepEqual(V.buildDict(latin).dict, vi);               // file trong repo đúng là đầu ra của công cụ
});

test("mọi chữ Việt + chữ số + ký hiệu bảng công đều có; nhãn thật đều học được", () => {
  const S = new Set(vi);
  V.vietnameseLetters().concat(V.SYMBOLS).forEach((c) => assert.ok(S.has(c), "thiếu " + c));
  for (const label of ["Phạm Minh Khoa", "Đỗ Thu Hằng", "BẢNG CHẤM CÔNG THÁNG 09/2026", "Tổng công", "Nguyễn Thị Phượng", "Giờ vào 7h - 15h", "0,5", "1+2", "Lễ Quốc khánh (2/9)", "Ẩn Ỷ Ữ Ự"])
    assert.deepEqual(V.uncovered(label, S), [], label);
  assert.deepEqual(V.uncovered("Họ", S), []);              // nhãn dạng tổ hợp (NFD) được chuẩn hóa NFC trước khi kiểm
  assert.deepEqual(V.uncovered("Phạm", latin), ["ạ"]);          // từ điển latin gốc thiếu chữ có dấu nặng
});
