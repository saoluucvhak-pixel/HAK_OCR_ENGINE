// Luồng phụ OCR (worker_threads) — bọc worker gốc của tesseract.js 5.1.1.
// Trong Electron, tesseract.js tự nhận là "electron" và coi langPath (thư mục trên máy) là URL → cố tải qua mạng, treo.
// Ở đây là luồng phụ của tiến trình chính (Node đầy đủ) → báo cho thư viện đây là Node để đọc dữ liệu ngôn ngữ từ đĩa. Không tải gì từ mạng.
// File nằm trong ocr/ (ngoài asar: build.asarUnpack) vì worker_threads không chạy được file trong asar.
"use strict";
const Module = require("module");
const path = require("path");
const tdir = path.dirname(require.resolve("tesseract.js/package.json"));
const isElectronId = require.resolve("is-electron", { paths: [tdir] });
const stub = new Module(isElectronId);
stub.filename = isElectronId; stub.loaded = true; stub.exports = () => false;
require.cache[isElectronId] = stub;
require(path.join(tdir, "src", "worker-script", "node", "index.js"));
