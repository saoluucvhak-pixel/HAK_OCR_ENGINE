"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), path = require("node:path");
const R = require("../../core/page-rectify.js"), G = require("../../core/table-grid.js"), TO = require("../../core/timesheet-ocr.js");
const { readGrayPNG } = require("../helpers/png.js");
const FIX = path.join(__dirname, "../fixtures/rectify");

/** Lưới ROWS × COLS ô vẽ thẳng bằng phép biến đổi map(u, v) cho trước (độc lập với module cần kiểm tra). */
const ROWS = 6, COLS = 15, CW = 90, CH = 60, OX = 120, OY = 140;
function grid(w, h, map) {
  const g = new Uint8Array(w * h).fill(255);
  const dot = (u, v) => { const [x, y] = map(u, v); for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const X = Math.round(x) + dx, Y = Math.round(y) + dy; if (X >= 0 && Y >= 0 && X < w && Y < h) g[Y * w + X] = 0; } };
  for (let r = 0; r <= ROWS; r++) for (let u = 0; u <= COLS * CW; u += 0.25) dot(OX + u, OY + r * CH);
  for (let c = 0; c <= COLS; c++) for (let v = 0; v <= ROWS * CH; v += 0.25) dot(OX + c * CW, OY + v);
  // vài "dòng chữ" tiêu đề phía trên bảng (không phải đường kẻ dài)
  for (let i = 0; i < 12; i++) for (let u = 0; u < 30; u += 0.5) for (let v = 0; v < 14; v += 0.5) if ((u + v) % 7 < 2) dot(OX + 40 + i * 45 + u, OY - 60 + v);
  return { g, w, h };
}
const rot = (deg, cx, cy) => { const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a); return (u, v) => [cx + (u - cx) * c - (v - cy) * s, cy + (u - cx) * s + (v - cy) * c]; };
const cellsOf = (img) => G.findCells(G.binarize(img.g, img.w, img.h), img.w, img.h).cells;
const W = 1700, H = 700;

test("ảnh thẳng: không nắn, trả lại đúng ảnh gốc", () => {
  const img = grid(W, H, (u, v) => [u, v]), r = R.rectify(img.g, img.w, img.h);
  assert.equal(r.applied, false); assert.equal(r.status, "STRAIGHT"); assert.equal(r.g, img.g);
});

test("nghiêng 3°: ước lượng góc đúng (±0,25°), sau khi nắn tìm đủ 90 ô cùng kích thước với ảnh thẳng", () => {
  const ref = cellsOf(grid(W, H, (u, v) => [u, v])), rw = ref[0].x1 - ref[0].x0, rh = ref[0].y1 - ref[0].y0;   // ô đo trên ảnh thẳng (trừ bề dày nét kẻ)
  const img = grid(W, H, rot(3, W / 2, H / 2)), r = R.rectify(img.g, img.w, img.h);
  assert.equal(r.applied, true); assert.ok(Math.abs(r.angle - 3) < 0.25, "góc " + r.angle);
  const cells = cellsOf(r);
  assert.equal(ref.length, ROWS * COLS); assert.equal(cells.length, ROWS * COLS);
  cells.forEach((c) => { assert.ok(Math.abs(c.x1 - c.x0 - rw) <= 2 && Math.abs(c.y1 - c.y0 - rh) <= 2, JSON.stringify(c) + " so với " + rw + "×" + rh); });
});

test("phối cảnh (cạnh trên hẹp hơn 8%): nắn thành hình chữ nhật, mọi ô cùng kích thước", () => {
  const top = OY, bot = OY + ROWS * CH, x0 = OX, x1 = OX + COLS * CW, k = 0.08 * (x1 - x0) / 2;
  const persp = (u, v) => { const t = (v - top) / (bot - top), shrink = k * (1 - t), cx = (x0 + x1) / 2; return [cx + (u - cx) * (1 - 2 * shrink / (x1 - x0)), v]; };
  const r = R.rectify(...Object.values(grid(W, H, persp)));
  assert.equal(r.applied, true); assert.equal(r.perspective, true);
  const cells = cellsOf(r), ws = cells.map((c) => c.x1 - c.x0);
  assert.equal(cells.length, ROWS * COLS);
  assert.ok(Math.max(...ws) - Math.min(...ws) <= 4, "độ rộng ô " + Math.min(...ws) + "…" + Math.max(...ws));
});

test("không có đường kẻ bảng: không nắn, ghi lý do", () => {
  const g = new Uint8Array(800 * 400).fill(255); for (let i = 0; i < 4000; i++) g[(i * 7919) % g.length] = 0;
  const r = R.rectify(g, 800, 400);
  assert.equal(r.applied, false); assert.equal(r.status, "NO_TABLE_LINES"); assert.equal(r.g, g);
});

test("nghiêng quá lớn (25°): không tự nắn, để người dùng xoay / chụp lại", () => {
  const r = R.rectify(...Object.values(grid(2000, 1400, rot(25, 1000, 700))));
  assert.equal(r.applied, false); assert.equal(r.status, "ANGLE_OUT_OF_RANGE");
});

test("ảnh bảng chấm công xấu (nghiêng 2° / 5°, phối cảnh, chụp điện thoại): sau khi nắn tìm đủ số ô như ảnh gốc", () => {
  const base = readGrayPNG(path.join(FIX, "00-goc.png")), want = cellsOf(base).length;
  assert.equal(R.rectify(base.g, base.w, base.h).applied, false);
  for (const name of ["01-nghieng-2do", "02-nghieng-5do", "10-phoi-canh-4pt", "12-chup-dien-thoai"]) {
    const img = readGrayPNG(path.join(FIX, name + ".png")), s = G.autoScale(img.w, img.h, 2400), z = G.resize(img.g, img.w, img.h, s);
    const r = R.rectify(z.g, z.w, z.h);
    assert.equal(r.applied, true, name + " " + r.status);
    assert.equal(cellsOf(r).length, want, name);
  }
});

test("ảnh chụp rất xấu (độ phân giải 60%, mờ, bóng đổ, nghiêng −3,5°): nắn không bao giờ làm mất ô so với không nắn", () => {
  const img = readGrayPNG(path.join(FIX, "13-chup-dien-thoai-xau.png")), s = G.autoScale(img.w, img.h, 2400), z = G.resize(img.g, img.w, img.h, s);
  const r = R.rectify(z.g, z.w, z.h), before = cellsOf(z).length;
  assert.equal(r.applied, true, r.status);
  assert.ok(cellsOf(r).length >= before, cellsOf(r).length + " < " + before);
});

test("analyze: kết quả ghi lại việc nắn (góc, phối cảnh, 4 góc nguồn); opt.rectify = false thì bỏ qua", async () => {
  const img = readGrayPNG(path.join(FIX, "02-nghieng-5do.png"));
  const host = { ocr: (items) => Promise.resolve(items.map(() => ({ text: "", conf: 0, good: 0 }))) };
  const r = await TO.analyze(img, host, { rotate: 0 });
  assert.equal(r.rectify.applied, true); assert.ok(Math.abs(r.rectify.angle + 5) < 0.5 || Math.abs(r.rectify.angle - 5) < 0.5, "góc " + r.rectify.angle);
  assert.equal(r.rectify.corners.length, 4);
  assert.ok(r.table.warnings.some((w) => /nắn thẳng/.test(w)), JSON.stringify(r.table.warnings));
  const off = await TO.analyze(img, host, { rotate: 0, rectify: false });
  assert.equal(off.rectify.applied, false); assert.equal(off.rectify.status, "DISABLED");
});
