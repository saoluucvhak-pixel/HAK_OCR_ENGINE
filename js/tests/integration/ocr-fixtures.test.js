// OCR thật (Tesseract offline, dữ liệu ngôn ngữ đóng gói ở ocr/lang) trên ảnh MẪU GIẢ LẬP (tests/fixtures/ocr, sinh bằng make_fixtures.py).
// Kiểm tra cả chuỗi: tìm ô → đoán chiều → OCR → dựng bảng → so tổng. Không dùng ảnh thật của người dùng.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs"), path = require("path"), zlib = require("zlib"), { Buffer } = require("buffer");
const G = require("../../core/table-grid.js");
const TO = require("../../core/timesheet-ocr.js");
const { createOcrService } = require("../../main/ocr-service.js");
const APP = path.resolve(__dirname, "../.."), FIX = path.join(APP, "tests/fixtures/ocr");

/** Giải mã PNG xám 8 bit (ảnh mẫu do Pillow lưu, chế độ "L") */
function readGrayPNG(file) {
  const b = fs.readFileSync(file); let p = 8, w = 0, h = 0; const idat = [];
  while (p < b.length) {
    const len = b.readUInt32BE(p), type = b.toString("ascii", p + 4, p + 8), d = b.subarray(p + 8, p + 8 + len);
    if (type === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); assert.ok(d[8] === 8 && d[9] === 0 && d[12] === 0, "chỉ hỗ trợ PNG xám 8 bit"); }
    if (type === "IDAT") idat.push(d);
    p += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat)), g = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (w + 1)], row = raw.subarray(y * (w + 1) + 1, (y + 1) * (w + 1));
    for (let x = 0; x < w; x++) {
      const a = x ? g[y * w + x - 1] : 0, up = y ? g[(y - 1) * w + x] : 0, c = x && y ? g[(y - 1) * w + x - 1] : 0;
      let v = row[x];
      if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const pp = a + up - c, pa = Math.abs(pp - a), pb = Math.abs(pp - up), pc = Math.abs(pp - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c; }
      g[y * w + x] = v & 255;
    }
  }
  return { g, w, h };
}

let svc;
test.before(() => { svc = createOcrService({ appDir: APP }); });
test.after(async () => { if (svc) await svc.terminate(); });
const host = { ocr: (items) => svc.batch(items) };

test("I-OCR-01 Tesseract offline chạy được với dữ liệu ngôn ngữ đóng gói", async () => {
  const r = await svc.selfTest();
  assert.ok(r.ok && /12/.test(r.text), JSON.stringify(r));
});

test("I-OCR-02 bảng in người × ngày: đúng tên, đúng từng ngày (cả 0.5), khớp cột Tổng công, nhận kỳ 09/2026", { timeout: 120000 }, async () => {
  const r = await TO.analyze(readGrayPNG(path.join(FIX, "bang-cham-cong-mau.png")), host);
  const T = r.table;
  assert.strictEqual(r.rot, 0); assert.strictEqual(r.period, "2026-09");
  assert.strictEqual(T.layout, "A"); assert.strictEqual(T.days.length, 30);
  assert.deepStrictEqual(T.lines.map((l) => l.name), ["E2E Nhân Viên", "Phạm Minh Khoa", "Đỗ Thu Hằng"]);
  assert.deepStrictEqual(T.lines.map((l) => l.sum), [28.5, 20, 15]);
  assert.strictEqual(T.lines[0].values[27], 0.5); assert.strictEqual(T.lines[1].values[3], null);
  T.lines.forEach((l) => assert.ok(l.check.length === 1 && l.check[0].ok && l.check[0].label === "Tổng công", JSON.stringify(l.check)));
});

test("I-OCR-03 lịch làm dọc, nét '1' viết tay: Công 30 / Cơm 28 khớp dòng TC; ảnh xoay 90° vẫn tự nhận đúng chiều", { timeout: 180000 }, async () => {
  const img = readGrayPNG(path.join(FIX, "lich-lam-doc-mau.png"));
  const check = (r) => {
    const T = r.table, cong = T.lines.find((l) => l.kind === "Công"), com = T.lines.find((l) => l.kind === "Cơm");
    assert.strictEqual(T.layout, "B"); assert.strictEqual(T.days.length, 30);
    assert.strictEqual(cong.sum, 30); assert.strictEqual(com.sum, 28);
    assert.strictEqual(com.values[10], null); assert.strictEqual(com.values[21], null);
    assert.ok(cong.check[0].ok && com.check[0].ok);
  };
  check(await TO.analyze(img, host));
  const rot = G.rotate90(img.g, img.w, img.h, 1); // giả lập ảnh chụp xoay ngang
  const r2 = await TO.analyze({ g: rot.g, w: rot.w, h: rot.h }, host);
  assert.notStrictEqual(r2.rot, 0, "phải tự xoay lại");
  check(r2);
});

test("I-OCR-04 trang PDF do pdf.js vẽ (nền xám nhạt, nhiễu nén JPEG, khử răng cưa): vẫn đọc đúng từng ô '1'", { timeout: 120000 }, async () => {
  // ảnh = trang bang-cham-cong-mau.pdf do app vẽ bằng pdf.js (2400 điểm) — trước α20 bản sửa: "1" đọc thành 9 / 3 / 5
  const r = await TO.analyze(readGrayPNG(path.join(FIX, "bang-cham-cong-mau-pdfjs.png")), host);
  assert.deepStrictEqual(r.table.lines.map((l) => l.sum), [28.5, 20, 15]);
  r.table.lines.forEach((l) => assert.ok(l.check[0] && l.check[0].ok && l.unreadable === 0));
});

// α22 — giá trị mong đợi in ra bằng: EXPECT=1 python3 tests/fixtures/ocr/make_fixtures.py
const MARKS = {
  "Lê Văn An": [2, 3, 2, 2, 3, 3, 0, 1, 1, 3, 2, 3, 1, 0, 0, 2, 1, 1, 0, 3, 0, 0, 3, 2, 2, 3, 1, 0, 3, 0],
  "Trần Bình": [3, 0, 0, 0, 1, 1, 0, 3, 1, 2, 1, 2, 3, 0, 1, 3, 1, 1, 2, 0, 0, 0, 2, 1, 2, 3, 0, 0, 1, 1], // ngày 9 ghi "7h-15h" = 8 giờ = 1 công
  "Ngô Cường": [1, 3, 1, 0, 0, 3, 0, 0, 2, 0, 1, 2, 0, 0, 0, 0, 1, 1, 0, 2, 0, 2, 2, 2, 0, 3, 1, 0, 1, 1],
};
test("I-OCR-05 bảng chấm công tay của tổ: 2 khối ngày, mỗi người 1 cột, dấu x (x/xx/xxx = 1/2/3 công), ô '7h-15h' = 1 công", { timeout: 180000 }, async () => {
  const r = await TO.analyze(readGrayPNG(path.join(FIX, "cham-cong-tay-x-mau.png")), host, { cellMode: "mark" });
  const T = r.table;
  assert.strictEqual(r.cellMode, "mark"); assert.strictEqual(r.period, "2026-09");
  assert.strictEqual(T.layout, "B"); assert.strictEqual(T.panels, 2); assert.deepStrictEqual(T.days, Array.from({ length: 30 }, (_, i) => i + 1));
  assert.deepStrictEqual(T.lines.map((l) => [l.name, l.kind]), Object.keys(MARKS).map((n) => [n, "Công"]));
  T.lines.forEach((l) => MARKS[l.name].forEach((v, i) => assert.strictEqual(l.values[i + 1], v || null, l.name + " ngày " + (i + 1))));
  assert.strictEqual(T.lines[1].cells[9].valSrc, "giờ 8");
  assert.deepStrictEqual(T.warnings, []);
});

test("I-OCR-06 lịch làm theo ca: 1 / 2 / 3 = 1 công, '1+2' = 2 công, X = nghỉ; tên người ở tiêu đề cột", { timeout: 180000 }, async () => {
  const r = await TO.analyze(readGrayPNG(path.join(FIX, "lich-ca-mau.png")), host, { cellMode: "ca" });
  const T = r.table, exp = {
    "Phan Thị Dung": [1, 1, 1, 2, null, 1, null, 1, 2, 1, 1, null, 1, 1, 1],
    "Hồ Văn Em": [1, null, 1, 1, 2, null, 1, 1, 1, null, 2, 1, 1, 1, 1],
  };
  assert.strictEqual(T.layout, "B"); assert.strictEqual(T.days.length, 15);
  assert.deepStrictEqual(T.lines.map((l) => l.name), Object.keys(exp));
  T.lines.forEach((l) => exp[l.name].forEach((v, i) => assert.strictEqual(l.values[i + 1], v, l.name + " ngày " + (i + 1))));
  assert.strictEqual(T.lines[0].cells[5].valSrc, "X = nghỉ");
});
