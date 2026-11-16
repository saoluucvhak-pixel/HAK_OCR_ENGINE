// Đo THẬT thư viện mẫu OCR (V7). Chạy: node tests/perf/ocr-library-bench.js [--no-tess]
// ⚠ Dữ liệu là chữ số TỔNG HỢP (tests/fixtures/synth-digits.js) — đo tốc độ / quy mô là số thật trên máy này,
//   còn "độ chính xác" chỉ là cận trên của cơ chế (cùng bộ sinh ảnh), KHÔNG phải độ chính xác trên chữ viết tay thật.
"use strict";
const fs = require("fs"), os = require("os"), path = require("path");
const S = require("../fixtures/synth-digits.js"), F = require("../../core/ocr-learning/features.js"), L = require("../../core/ocr-learning/library.js");
const { createStore } = require("../../main/ocr-library.js");
const ms = (t) => Math.round(Number(process.hrtime.bigint() - t) / 1e4) / 100;
const LAB = "0123456789".split("");
const out = { env: { node: process.version, cpu: os.cpus()[0].model, cores: os.cpus().length, mem_mb: Math.round(os.totalmem() / 1048576) } };
function vecs(n, seed) { const rng = S.prng(seed), r = []; for (let i = 0; i < n; i++) { const l = LAB[i % 10], im = S.render(l, rng); r.push({ l, im, f: F.extract(im.g, im.w, im.h) }); } return r; }

// A) Tra cứu theo quy mô thư viện (in-memory, chỉ mục thô 16 chiều → lọc → so khớp đầy đủ)
{
  const rows = [], q = vecs(300, 999);
  for (const N of [100, 1000, 10000, 50000]) {
    const lib = L.createLibrary(), pool = vecs(Math.min(N, 5000), 1), rng = S.prng(N);
    let t = process.hrtime.bigint();
    for (let i = 0; i < N; i++) { const p = pool[i % pool.length], v = Float32Array.from(p.f.vec, (x) => x + (rng() - 0.5) * 0.02); lib.apply({ t: "sample", id: "S" + i, status: "VERIFIED", cellType: "digit", label: p.l, labelKind: "SYMBOL", source: "CORRECTED", vec: v, pngSha: "h" + i, createdAt: "t" }); }
    const tLoad = ms(t); t = process.hrtime.bigint(); lib.lookup(q[0].f.vec, "digit"); const tIdx = ms(t); // lần đầu dựng chỉ mục
    t = process.hrtime.bigint(); q.forEach((x) => lib.lookup(x.f.vec, "digit")); const per = ms(t) / q.length;
    rows.push({ samples: N, "nạp bộ nhớ (ms)": tLoad, "dựng chỉ mục (ms)": tIdx, "tra cứu / ô (ms)": +per.toFixed(2), "ô / giây": Math.round(1000 / per) });
  }
  out.lookupScaling = rows; console.table(rows);
}
// B) 500 lần sửa ghi bền xuống đĩa (ảnh PNG + nhật ký fsync) + nạp lại
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "olb-")), st = createStore(dir), rng = S.prng(42); let t = process.hrtime.bigint();
  for (let i = 0; i < 500; i++) { const l = LAB[i % 10], im = S.render(l, rng); st.record({ raw: im.g, clean: im.g, w: im.w, h: im.h, cellType: "digit", docId: "D" + (i % 5), page: 1, bbox: { x0: i, y0: i, x1: i + 5, y1: i + 5 }, after: l, before: "", mode: "so" }); }
  const tRec = ms(t); t = process.hrtime.bigint(); st.approve({}); const tApp = ms(t);
  t = process.hrtime.bigint(); const st2 = createStore(dir); st2.load(); const tLoad = ms(t); t = process.hrtime.bigint(); const v = st2.verify(); const tVer = ms(t);
  const sz = (d) => fs.readdirSync(d, { withFileTypes: true }).reduce((s, e) => s + (e.isDirectory() ? sz(path.join(d, e.name)) : fs.statSync(path.join(d, e.name)).size), 0);
  out.persist500 = { "ghi 500 lần sửa (ms)": tRec, "ms / lần sửa": +(tRec / 500).toFixed(2), "duyệt (ms)": tApp, "nạp lại từ đĩa (ms)": tLoad, "kiểm toàn vẹn (ms)": tVer, ok: v.ok, "dung lượng (KB)": Math.round(sz(dir) / 1024), samples: st2.lib.size() };
  console.log("500 lần sửa:", out.persist500);
}
// C) Hiệu chỉnh ngưỡng trên tập RIÊNG rồi đo trên tập TEST (3 tập khác nhau: mẫu thư viện / hiệu chỉnh / kiểm tra)
(async () => {
  const lib = L.createLibrary(); let n = 0;
  vecs(200, 11).forEach((p) => lib.apply({ t: "sample", id: "S" + (n++), status: "VERIFIED", cellType: "digit", label: p.l, labelKind: "SYMBOL", source: "CORRECTED", vec: p.f.vec, pngSha: "h" + n, createdAt: "t" }));
  const hard = (seed) => { const rng = S.prng(seed), r = []; for (let i = 0; i < 1000; i++) { const l = LAB[i % 10], im = S.render(l, rng, { jitter: 0.09, noise: 14 }); r.push({ l, f: F.extract(im.g, im.w, im.h) }); } return r; };
  const calib = hard(21), test = hard(22);
  const run = (set, th) => { lib.cfg.autoThreshold = th; let auto = 0, wrong = 0, sug = 0, unr = 0; set.forEach((x) => { const r = lib.lookup(x.f.vec, "digit"); if (r.status === "AUTO_ACCEPT") { auto++; if (r.label !== x.l) wrong++; } else if (r.status === "SUGGESTED") sug++; else unr++; }); return { th, auto, wrong, sug, unr, autoPrecision: auto ? +(100 * (auto - wrong) / auto).toFixed(2) : 100 }; };
  const sweep = [0.78, 0.82, 0.86, 0.9, 0.93, 0.95, 0.97].map((th) => run(calib, th)); console.table(sweep);
  const knee = sweep.filter((r) => r.autoPrecision >= 99.5).sort((a, b) => b.auto - a.auto)[0] || sweep[sweep.length - 1];
  // dữ liệu tổng hợp tách bạch quá dễ (100% ở mọi ngưỡng) nên KHÔNG dùng để hạ ngưỡng: giữ sàn an toàn 0,93 cho tới khi có dữ liệu thật
  const chosen = sweep.find((r) => r.th >= Math.max(0.93, knee.th)) || sweep[sweep.length - 1];
  const res = run(test, chosen.th); out.calibration = { sweep, chosen: chosen.th, testResult: res, note: "ngưỡng chọn trên tập hiệu chỉnh (precision AUTO ≥ 99,5%) nhưng không thấp hơn sàn an toàn 0,93; đo lại trên tập test riêng; dữ liệu tổng hợp — cần hiệu chỉnh lại trên chứng từ thật" };
  console.log("TEST với ngưỡng", chosen.th, res);
  // D) Tesseract một mình vs Tesseract + thư viện trên tập test (nếu có)
  if (!process.argv.includes("--no-tess")) {
    try {
      const { createOcrService } = require("../../main/ocr-service"), svc = createOcrService({ appDir: path.join(__dirname, "..", "..") });
      const rng = S.prng(23), items = [], truth = [], fv = []; for (let i = 0; i < 300; i++) { const l = LAB[i % 10], im = S.render(l, rng, { jitter: 0.09, noise: 14 }); items.push({ w: im.w, h: im.h, data: im.g, mode: "digit" }); truth.push(l); fv.push(F.extract(im.g, im.w, im.h)); }
      const o = await svc.batch(items); lib.cfg.autoThreshold = chosen.th; let tess = 0, comb = 0, libAuto = 0, libAutoWrong = 0;
      o.forEach((r, i) => { const tt = String(r.text || "").replace(/\D/g, ""); if (tt === truth[i]) tess++; const lr = lib.lookup(fv[i].vec, "digit", { ocrText: tt, ocrConf: r.conf }); let final = tt; if (lr.status === "AUTO_ACCEPT") { libAuto++; if (lr.label !== truth[i]) libAutoWrong++; final = lr.label; } else if (lr.status === "SUGGESTED" && tt !== lr.label && (r.conf || 0) < 60) final = lr.label; if (final === truth[i]) comb++; });
      out.accuracy = { n: 300, "Tesseract một mình (%)": +(100 * tess / 300).toFixed(1), "Tesseract + thư viện (%)": +(100 * comb / 300).toFixed(1), libAuto, libAutoWrong, note: "chữ số tổng hợp, thư viện 200 mẫu — cận trên của cơ chế, KHÔNG phải độ chính xác trên chữ viết tay thật" };
      console.log("So sánh độ chính xác:", out.accuracy); await svc.terminate();
    } catch (e) { out.accuracy = { error: String(e.message || e) }; console.log("Bỏ qua so sánh Tesseract:", e.message); }
  }
  fs.writeFileSync(path.join(__dirname, "last-ocr-library-bench.json"), JSON.stringify(out, null, 1)); console.log("→ tests/perf/last-ocr-library-bench.json");
})();
