// ===== MAIN / UMI-OCR — ý kiến thứ hai cho ô SỐ, qua API HTTP cục bộ của Umi-OCR (https://github.com/hiroi-sora/Umi-OCR, MIT) =====
// Umi-OCR (PaddleOCR / RapidOCR) do người dùng tự cài và tự chạy; app chỉ gọi POST /api/ocr trên máy này (127.0.0.1:1224 mặc định).
// - Chỉ chấp nhận địa chỉ loopback: ảnh ô chấm công KHÔNG rời khỏi máy.
// - Không thay kết quả Tesseract: chỉ ghi secondOpinion (AGREE / DISAGREE + gợi ý / NO_TEXT / NOT_NUMERIC / UNAVAILABLE) để người duyệt quyết định.
// - Đo trên ảnh giả lập: Umi-OCR (RapidOCR, model English) đọc đúng "0,5" ở nhiều ảnh Tesseract đọc thành "05"; nhưng KÉM Tesseract trên ảnh mờ / nhỏ
//   và không có model tiếng Việt → chỉ dùng cho ô số, không dùng cho tên.
"use strict";
const http = require("http");

const LOOPBACK = { "127.0.0.1": 1, localhost: 1, "::1": 1 };

/** opts: { host = 127.0.0.1, port = 1224, timeoutMs = 4000, language = "English" } */
function createUmiClient(opts) {
  opts = opts || {};
  const host = opts.host || "127.0.0.1", port = opts.port || 1224, timeoutMs = opts.timeoutMs || 4000, language = opts.language || "English";
  // ngắt mạch: Umi-OCR không chạy / không trả lời → bỏ qua trong cooldownMs (không thử lại từng ô của trang)
  const cooldownMs = opts.cooldownMs == null ? 30000 : opts.cooldownMs, now = opts.now || Date.now;
  let downUntil = 0;
  if (!LOOPBACK[host]) throw new Error("Umi-OCR chỉ được gọi trên máy cục bộ (127.0.0.1 / localhost / ::1), không gửi ảnh chấm công ra ngoài: " + host);
  function call(method, path, payload) {
    return new Promise((ok) => {
      const body = payload ? JSON.stringify(payload) : null, done = (v) => { if (!fin) { fin = true; ok(v); } };
      let fin = false;
      const rq = http.request({ host, port, path, method, headers: body ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } : {} }, (rs) => {
        let s = ""; rs.setEncoding("utf8"); rs.on("data", (d) => { s += d; if (s.length > 4e6) rq.destroy(); });
        rs.on("end", () => { try { done({ ok: rs.statusCode === 200, json: JSON.parse(s) }); } catch (e) { done({ ok: false, error: "invalid JSON" }); } });
      });
      rq.setTimeout(timeoutMs, () => { rq.destroy(); done({ ok: false, error: "timeout" }); });
      rq.on("error", (e) => done({ ok: false, error: String(e.code || e.message || e) }));
      rq.end(body || undefined);
    });
  }
  return {
    host, port,
    /** Umi-OCR có đang chạy không → { ok, languages[] } */
    async probe() {
      const r = await call("GET", "/api/ocr/get_options");
      const lang = r.ok && r.json && r.json["ocr.language"];
      return r.ok && lang ? { ok: true, languages: (lang.optionsList || []).map((o) => o[0]) } : { ok: false, error: r.error || "not Umi-OCR" };
    },
    /** png: Buffer → { status: OK | NO_TEXT | UNAVAILABLE, text?, score? } */
    async read(png) {
      if (now() < downUntil) return { status: "UNAVAILABLE", error: "skipped (Umi-OCR not responding)" };
      const r = await call("POST", "/api/ocr", { base64: Buffer.from(png).toString("base64"), options: { "ocr.language": language, "tbpu.parser": "single_line", "data.format": "dict" } });
      if (!r.ok && r.error && r.error !== "invalid JSON") downUntil = now() + cooldownMs;
      if (!r.ok || !r.json) return { status: "UNAVAILABLE", error: r.error || "HTTP error" };
      if (r.json.code === 101) return { status: "NO_TEXT" };
      if (r.json.code !== 100 || !Array.isArray(r.json.data) || !r.json.data.length) return { status: "UNAVAILABLE", error: "code " + r.json.code };
      const d = r.json.data;
      return { status: "OK", text: d.map((x) => String(x.text || "") + (x.end || "")).join("").trim(), score: Math.round(1000 * d.reduce((a, x) => a + (+x.score || 0), 0) / d.length) / 1000 };
    },
  };
}

/** "0,5" / "0.5" / "1" → số; không phải số đơn giản → NaN */
function num(t) { const s = String(t == null ? "" : t).replace(/\s+/g, ""); return /^\d+(?:[.,]\d+)?$/.test(s) ? Number(s.replace(",", ".")) : NaN; }

/** Gắn ý kiến thứ hai vào kết quả Tesseract của 1 ô số (giữ nguyên text / conf gốc). */
function compare(reading, umi) {
  const op = { engine: "umi-ocr", status: umi && umi.status === "OK" ? "" : (umi && umi.status) || "UNAVAILABLE", offered: false };
  if (umi && umi.status === "OK") {
    const u = num(umi.text), t = num(reading.text);
    op.text = isNaN(u) ? umi.text : String(u).replace(".", ","); op.score = umi.score;
    if (isNaN(u)) op.status = "NOT_NUMERIC";
    else if (u === t) op.status = "AGREE";
    else { op.status = "DISAGREE"; op.offered = true; }
  }
  return Object.assign({}, reading, { secondOpinion: op });
}

module.exports = { createUmiClient, compare };
