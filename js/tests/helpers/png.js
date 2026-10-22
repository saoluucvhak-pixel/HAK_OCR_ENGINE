"use strict";
// Giải mã PNG xám 8 bit (ảnh Pillow chế độ "L") cho test — không cần thư viện ngoài.
const fs = require("node:fs"), zlib = require("node:zlib");
function readGrayPNG(file) {
  const b = fs.readFileSync(file); let p = 8, w = 0, h = 0; const idat = [];
  while (p < b.length) {
    const len = b.readUInt32BE(p), type = b.toString("ascii", p + 4, p + 8), d = b.subarray(p + 8, p + 8 + len);
    if (type === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); if (!(d[8] === 8 && d[9] === 0 && d[12] === 0)) throw Error("chỉ hỗ trợ PNG xám 8 bit"); }
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
module.exports = { readGrayPNG };
