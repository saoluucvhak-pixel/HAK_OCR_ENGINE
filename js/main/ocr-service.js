// ===== MAIN / OCR-SERVICE — đọc chữ / số trong ô bảng chấm công bằng Tesseract (chạy OFFLINE trong tiến trình chính) — 2.0-α20 =====
// - Giao diện cắt sẵn từng ô (ảnh xám nhỏ) rồi gửi theo lô; ở đây mã hóa PNG + nhận dạng, trả { text, conf }.
// - Dữ liệu ngôn ngữ đi kèm app (ocr/lang: vie, eng — tessdata_best_int qua @tesseract.js-data, giấy phép Apache-2.0 / MIT).
// - Không gửi ảnh ra mạng; không ghi ảnh xuống đĩa.
"use strict";
const path = require("path");
const zlib = require("zlib");
const { Buffer } = require("buffer");
const U = require("./umi-ocr.js");

// ---------- PNG xám tối giản (không cần thư viện) ----------
const CRC = (() => { const t = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c; } return t; })();
function crc32(buf) { let c = -1; for (let i = 0; i < buf.length; i++) c = CRC[(c ^ buf[i]) & 0xff] ^ (c >>> 8); return (c ^ -1) >>> 0; }
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, "ascii"), data]), crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
/** Ảnh xám (Uint8Array w×h) → PNG */
function encodeGrayPNG(gray, w, h) {
  const raw = Buffer.alloc((w + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w + 1)] = 0; for (let x = 0; x < w; x++) raw[y * (w + 1) + 1 + x] = gray[y * w + x]; }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 0; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

/** Đường dẫn thật cho file nằm trong gói app (asar → app.asar.unpacked, vì luồng phụ của Tesseract không đọc được trong asar) */
function unpacked(p) { return p.replace(/app\.asar([\\/])/, "app.asar.unpacked$1"); }

/**
 * opts.appDir: thư mục app (chứa ocr/lang); opts.tesseract: thư viện (mặc định require("tesseract.js"))
 * opts.secondOpinion: (tuỳ chọn) client của main/umi-ocr.js — ô SỐ được đọc thêm bằng Umi-OCR, kết quả ở reading.secondOpinion (không thay chữ Tesseract)
 * Trả { batch(items) → Promise<[{ text, conf }]>, selfTest(), terminate() }
 * items: [{ w, h, data: Uint8Array xám, mode: "digit" | "text" | "block" | "page" | "ca" }]
 */
function createOcrService(opts) {
  opts = opts || {};
  const T = opts.tesseract || require("tesseract.js");
  const langPath = unpacked(path.join(opts.appDir || path.join(__dirname, ".."), "ocr", "lang"));
  let workers = null, queue = Promise.resolve(), handwriting = null;
  const H = require("./handwritten-digits.js");
  function handwritingCandidate(reading, item) {
    const proxy = { recognize(crop) {
      if (!handwriting) handwriting = H.create(require(unpacked(path.join(__dirname, "..", "ocr", "models", "mnist-cnn.json"))));
      return handwriting.recognize(crop);
    } };
    return H.addCandidate(reading, item, proxy);
  }
  const wopts = () => {
    const o = { langPath, cacheMethod: "none", gzip: true };
    try {
      const cdir = path.dirname(require.resolve("tesseract.js-core/package.json"));
      o.workerPath = unpacked(path.join(opts.appDir || path.join(__dirname, ".."), "ocr", "worker.js")); // bọc worker gốc (xem ocr/worker.js)
      o.corePath = unpacked(cdir);
    } catch (e) { /* để thư viện tự tìm */ }
    return o;
  };
  async function init() {
    if (workers) return workers;
    const o = wopts();
    const text = await T.createWorker("vie", 1, o);
    await text.setParameters({ tessedit_pageseg_mode: T.PSM.SINGLE_LINE, preserve_interword_spaces: "1" });
    const digit = await T.createWorker("eng", 1, o);
    await digit.setParameters({ tessedit_pageseg_mode: T.PSM.SINGLE_WORD, tessedit_char_whitelist: "0123456789.,/" });
    workers = { text, digit, page: null, block: null, ca: null };
    return workers;
  }
  async function run(items) {
    const ws = await init(), out = [];
    for (const it of items || []) {
      if (!it || !it.w || !it.h || !it.data) { out.push({ text: "", conf: 0 }); continue; }
      const data = it.data instanceof Uint8Array ? it.data : Uint8Array.from(it.data);
      if (it.mode === "page" || it.mode === "document") { // cả trang (đoán chiều ảnh): đếm từ đọc chắc (≥ 3 chữ cái, tin cậy ≥ 70)
        if (!ws.page) { ws.page = await T.createWorker("vie", 1, wopts()); await ws.page.setParameters({ tessedit_pageseg_mode: T.PSM.AUTO }); }
        const rp = await ws.page.recognize(encodeGrayPNG(data, it.w, it.h));
        // chỉ đếm từ NẰM NGANG: Tesseract tự đọc được cả chữ dọc nên ảnh xoay 90° cũng ra từ (khung cao hơn rộng)
        const good = (rp.data.words || []).filter((x) => x.confidence >= 70 && (String(x.text).match(/[A-Za-zÀ-ỹ]/g) || []).length >= 3 && (!x.bbox || x.bbox.x1 - x.bbox.x0 > x.bbox.y1 - x.bbox.y0)).length;
        out.push({ text: it.mode === "document" ? String(rp.data.text || "") : "", conf: Math.round(rp.data.confidence || 0), good: good });
        continue;
      }
      if (it.mode === "ca" && !ws.ca) { ws.ca = await T.createWorker("eng", 1, wopts()); await ws.ca.setParameters({ tessedit_pageseg_mode: T.PSM.SINGLE_LINE, tessedit_char_whitelist: "0123456789+xX" }); } // lịch làm theo ca: "1+2", X
      if (it.mode === "block" && !ws.block) { ws.block = await T.createWorker("vie", 1, wopts()); await ws.block.setParameters({ tessedit_pageseg_mode: T.PSM.SINGLE_BLOCK }); } // nhãn 2 dòng ("Tổng / công")
      const png = encodeGrayPNG(data, it.w, it.h);
      const r = await (it.mode === "digit" ? ws.digit : it.mode === "block" ? ws.block : it.mode === "ca" ? ws.ca : ws.text).recognize(png);
      const reading = { text: String(r.data.text || "").replace(/\s+$/g, "").replace(/\n+/g, " ").trim(), conf: Math.round(r.data.confidence || 0) };
      if (it.mode !== "digit") { out.push(reading); continue; }
      const withHand = handwritingCandidate(reading, it);
      out.push(opts.secondOpinion ? U.compare(withHand, await opts.secondOpinion.read(png).catch(() => ({ status: "UNAVAILABLE" }))) : withHand);
    }
    return out;
  }
  return {
    // chạy tuần tự (1 hàng đợi) — nhiều lô gửi cùng lúc không tranh worker
    batch(items) { const p = queue.then(() => run(items)); queue = p.catch(() => {}); return p; },
    /** Kiểm tra nhanh OCR chạy được trên máy (vẽ sẵn chữ số "12" bằng điểm ảnh) */
    async selfTest() {
      const w = 60, h = 40, g = new Uint8Array(w * h).fill(255);
      const bar = (x0, y0, x1, y1) => { for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) g[y * w + x] = 0; };
      bar(14, 8, 18, 32); bar(10, 8, 16, 12);                                   // 1
      bar(26, 8, 40, 11); bar(37, 8, 40, 20); bar(26, 18, 40, 21); bar(26, 18, 29, 32); bar(26, 29, 42, 32); // 2
      const t0 = Date.now(), r = (await this.batch([{ w, h, data: g, mode: "digit" }]))[0];
      return { ok: true, text: r.text, conf: r.conf, ms: Date.now() - t0, langPath, handwriting: r.handwriting };
    },
    async terminate() { if (workers) { const w = workers; workers = null; await w.text.terminate(); await w.digit.terminate(); if (w.page) await w.page.terminate(); if (w.block) await w.block.terminate(); if (w.ca) await w.ca.terminate(); } }
  };
}

const MODES = { digit: 1, text: 1, block: 1, page: 1, document: 1, ca: 1 };
/** Kiểm tra lô ô từ giao diện: giữ nguyên số phần tử; ô sai (kích thước, dữ liệu) → { w: 0 } (trả kết quả rỗng) */
function sanitizeOcrItems(items) {
  return items.map((it) => {
    const w = it && it.w | 0, h = it && it.h | 0, d = it && it.data;
    const okData = d && (d instanceof Uint8Array || Array.isArray(d)) && d.length === w * h;
    if (!(w > 0 && h > 0 && w * h <= 25e6 && okData)) return { w: 0, h: 0, data: null, mode: "text" };
    return { w, h, data: d, mode: MODES[it.mode] ? it.mode : "text" };
  });
}

module.exports = { createOcrService, sanitizeOcrItems, encodeGrayPNG, unpacked };
