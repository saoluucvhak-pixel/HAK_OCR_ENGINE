// Bộ ký tự huấn luyện PaddleOCR cho tiếng Việt: GIỮ NGUYÊN thứ tự từ điển latin của PP-OCRv5 (để tái dùng trọng số đã huấn luyện
// cho các lớp cũ) rồi THÊM vào cuối mọi chữ Việt còn thiếu (thường + hoa, dạng dựng sẵn NFC). Không sửa / xóa dòng cũ, kể cả dòng trùng.
// node vi-charset.cjs <ppocrv5_latin_dict.txt> <ra: vi_latin_dict.txt>
"use strict";
const fs = require("node:fs");

const BASE = "aăâeêioôơuưy";
const TONES = ["", "̀", "́", "̉", "̃", "̣"];   // ngang, huyền, sắc, hỏi, ngã, nặng
/** Mọi chữ cái tiếng Việt (NFC), chữ thường rồi chữ hoa. */
function vietnameseLetters() {
  const lower = ["đ"].concat("bcdghklmnpqrstvx".split(""));
  for (const v of BASE) for (const t of TONES) lower.push((v + t).normalize("NFC"));
  return lower.concat(lower.map((c) => c.toUpperCase()));
}
/** Ký hiệu bảng chấm công / giấy tờ phải đọc được. */
const SYMBOLS = "0123456789,./:-+×½()%".split("");

function readDict(file) { const lines = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n").split("\n"); if (lines[lines.length - 1] === "") lines.pop(); return lines; }
/** Từ điển latin → từ điển latin + chữ Việt / ký hiệu còn thiếu (giữ tiền tố). Trả { dict, added }. */
function buildDict(latin) {
  const have = new Set(latin), added = [];
  for (const c of vietnameseLetters().concat(SYMBOLS)) if (!have.has(c)) { have.add(c); added.push(c); }
  return { dict: latin.concat(added), added };
}
/** Ký tự của nhãn (sau NFC) không có trong bộ ký tự — nhãn như vậy không học được, phải bổ sung bộ ký tự hoặc sửa nhãn. */
function uncovered(label, dict) { const s = dict instanceof Set ? dict : new Set(dict); return Array.from(new Set(Array.from(String(label).normalize("NFC")).filter((c) => c !== " " && !s.has(c)))); }

module.exports = { vietnameseLetters, SYMBOLS, readDict, buildDict, uncovered };

if (require.main === module) {
  const [src, out] = process.argv.slice(2);
  const { dict, added } = buildDict(readDict(src));
  fs.writeFileSync(out, dict.join("\n") + "\n");
  console.log("Từ điển " + dict.length + " dòng (" + added.length + " ký tự thêm): " + added.join(""));
}
