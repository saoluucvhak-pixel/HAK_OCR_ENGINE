"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), http = require("node:http");
const U = require("../../main/umi-ocr.js");
const { createOcrService } = require("../../main/ocr-service.js");

/** Máy chủ giả lập API Umi-OCR (POST /api/ocr, GET /api/ocr/get_options) — trả lời theo hàm reply(body). */
function fakeUmi(reply, opt) {
  opt = opt || {};
  const seen = [];
  const srv = http.createServer((rq, rs) => {
    let s = ""; rq.on("data", (d) => (s += d)); rq.on("end", () => {
      if (rq.url === "/api/ocr/get_options") { rs.end(JSON.stringify({ "ocr.language": { optionsList: [["English", "English"], ["简体中文", "简体中文"]] } })); return; }
      const body = JSON.parse(s); seen.push(body);
      setTimeout(() => rs.end(JSON.stringify(reply(body))), opt.delay || 0);
    });
  });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({ port: srv.address().port, seen, close: () => new Promise((c) => srv.close(c)) })));
}
const png = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
const said = (text, score) => () => ({ code: 100, data: [{ text, score: score == null ? 0.98 : score, box: [[0, 0], [1, 0], [1, 1], [0, 1]], end: "" }] });

test("chỉ gọi máy cục bộ: địa chỉ ngoài loopback bị từ chối ngay khi tạo", () => {
  for (const host of ["192.168.1.5", "example.com", "10.0.0.1"]) assert.throws(() => U.createUmiClient({ host }), /cục bộ/);
  for (const host of ["127.0.0.1", "localhost", "::1"]) assert.equal(typeof U.createUmiClient({ host }).read, "function");
});

test("đọc ô: gửi base64 PNG + model English, trả chữ và điểm; không thấy chữ / lỗi / quá hạn → trạng thái rõ, không ném lỗi", async () => {
  const s = await fakeUmi(said("0.5", 0.97)), c = U.createUmiClient({ port: s.port });
  const r = await c.read(png);
  assert.deepEqual(r, { status: "OK", text: "0.5", score: 0.97 });
  assert.equal(s.seen[0].base64, png.toString("base64")); assert.equal(s.seen[0].options["ocr.language"], "English");
  await s.close();
  const none = await fakeUmi(() => ({ code: 101, data: "No text found" }));
  assert.equal((await U.createUmiClient({ port: none.port }).read(png)).status, "NO_TEXT"); await none.close();
  const bad = await fakeUmi(() => ({ code: 902, data: "engine crashed" }));
  assert.equal((await U.createUmiClient({ port: bad.port }).read(png)).status, "UNAVAILABLE"); await bad.close();
  const slow = await fakeUmi(said("1"), { delay: 300 });
  assert.equal((await U.createUmiClient({ port: slow.port, timeoutMs: 50 }).read(png)).status, "UNAVAILABLE"); await slow.close();
  assert.equal((await U.createUmiClient({ port: 1 }).read(png)).status, "UNAVAILABLE");   // không có Umi-OCR đang chạy
});

test("ngắt mạch: Umi-OCR không chạy → sau lần lỗi đầu, các ô sau bỏ qua ngay; hết thời gian chờ thì thử lại", async () => {
  let t = 1000; const c = U.createUmiClient({ port: 1, cooldownMs: 30000, now: () => t });
  assert.equal((await c.read(png)).status, "UNAVAILABLE");
  const r2 = await c.read(png); assert.equal(r2.status, "UNAVAILABLE"); assert.match(r2.error, /skipped/);
  const s = await fakeUmi(said("1")), c2 = U.createUmiClient({ port: s.port, cooldownMs: 30000, now: () => t });
  t = 1000; assert.equal((await c2.read(png)).status, "OK"); await s.close();
  t += 31000; const r3 = await c.read(png); assert.doesNotMatch(r3.error, /skipped/);   // hết chờ: thử kết nối lại
});

test("probe: nhận ra Umi-OCR đang chạy và danh sách ngôn ngữ; không chạy → ok = false", async () => {
  const s = await fakeUmi(said("1")), p = await U.createUmiClient({ port: s.port }).probe();
  assert.equal(p.ok, true); assert.deepEqual(p.languages, ["English", "简体中文"]); await s.close();
  assert.equal((await U.createUmiClient({ port: 1, timeoutMs: 200 }).probe()).ok, false);
});

test("ý kiến thứ hai: cùng số → AGREE; khác số → DISAGREE kèm gợi ý; giữ nguyên chữ / điểm Tesseract", () => {
  const t = { text: "05", conf: 81 };
  const d = U.compare(t, { status: "OK", text: "0.5", score: 0.97 });
  assert.equal(d.text, "05"); assert.equal(d.conf, 81);
  assert.deepEqual(d.secondOpinion, { engine: "umi-ocr", status: "DISAGREE", text: "0,5", score: 0.97, offered: true });
  assert.equal(U.compare({ text: "1", conf: 90 }, { status: "OK", text: "1", score: 0.99 }).secondOpinion.status, "AGREE");
  assert.equal(U.compare({ text: "0,5", conf: 90 }, { status: "OK", text: "0.5", score: 0.99 }).secondOpinion.status, "AGREE");
  assert.equal(U.compare({ text: "", conf: 0 }, { status: "OK", text: "1", score: 0.9 }).secondOpinion.offered, true);   // Tesseract bỏ trống → gợi ý
  const nn = U.compare({ text: "1", conf: 90 }, { status: "OK", text: "l", score: 0.9 }).secondOpinion;
  assert.equal(nn.status, "NOT_NUMERIC"); assert.equal(nn.offered, false);
  assert.equal(U.compare({ text: "1", conf: 90 }, { status: "UNAVAILABLE" }).secondOpinion.offered, false);
});

/** Tesseract giả: worker "digit" luôn đọc chữ cho trước */
function fakeTesseract(digitText) {
  const worker = (lang) => ({ setParameters: async () => {}, terminate: async () => {}, recognize: async () => ({ data: { text: digitText, confidence: 80, words: [] } }) });
  return { PSM: { SINGLE_LINE: 7, SINGLE_WORD: 8, AUTO: 3, SINGLE_BLOCK: 6 }, createWorker: async (lang) => worker(lang) };
}
const item = (mode) => ({ w: 10, h: 10, data: new Uint8Array(100).fill(255), mode });

test("ocr-service: chỉ ô số được hỏi ý kiến thứ hai; ô chữ / trang không gửi sang Umi-OCR; Umi lỗi không làm hỏng lô", async () => {
  const s = await fakeUmi(said("0.5")), svc = createOcrService({ appDir: __dirname, tesseract: fakeTesseract("05"), secondOpinion: U.createUmiClient({ port: s.port }) });
  const out = await svc.batch([item("digit"), item("text")]);
  assert.equal(out[0].text, "05"); assert.equal(out[0].secondOpinion.status, "DISAGREE"); assert.equal(out[0].secondOpinion.text, "0,5");
  assert.equal(out[1].secondOpinion, undefined); assert.equal(s.seen.length, 1);
  await svc.terminate(); await s.close();
  const off = createOcrService({ appDir: __dirname, tesseract: fakeTesseract("1"), secondOpinion: U.createUmiClient({ port: 1, timeoutMs: 100 }) });
  const o2 = await off.batch([item("digit")]);
  assert.equal(o2[0].text, "1"); assert.equal(o2[0].secondOpinion.status, "UNAVAILABLE"); await off.terminate();
  const none = createOcrService({ appDir: __dirname, tesseract: fakeTesseract("1") });
  assert.equal((await none.batch([item("digit")]))[0].secondOpinion, undefined); await none.terminate();
});
