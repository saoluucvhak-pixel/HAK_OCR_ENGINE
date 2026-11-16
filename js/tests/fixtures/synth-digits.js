// ẢNH CHỮ SỐ TỔNG HỢP (không phải chữ viết tay thật): nét đa tuyến + méo/dày/nhiễu ngẫu nhiên có hạt giống — chỉ để kiểm thử cơ chế
// tra cứu mẫu. KHÔNG dùng làm bằng chứng độ chính xác trên chứng từ thật (xem docs/OCR_V7_BAO_CAO.md).
"use strict";
function prng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
const P = {
  "0": [[0.5, 0.08], [0.78, 0.2], [0.85, 0.5], [0.78, 0.8], [0.5, 0.92], [0.22, 0.8], [0.15, 0.5], [0.22, 0.2], [0.5, 0.08]],
  "1": [[0.3, 0.28], [0.52, 0.1], [0.52, 0.92]],
  "2": [[0.2, 0.3], [0.35, 0.12], [0.65, 0.12], [0.8, 0.3], [0.2, 0.9], [0.85, 0.9]],
  "3": [[0.2, 0.15], [0.8, 0.15], [0.45, 0.5], [0.8, 0.65], [0.7, 0.9], [0.2, 0.88]],
  "4": [[0.7, 0.92], [0.7, 0.1], [0.15, 0.65], [0.9, 0.65]],
  "5": [[0.8, 0.12], [0.25, 0.12], [0.22, 0.48], [0.65, 0.45], [0.82, 0.68], [0.6, 0.9], [0.2, 0.85]],
  "6": [[0.75, 0.12], [0.3, 0.4], [0.2, 0.7], [0.4, 0.92], [0.7, 0.85], [0.75, 0.62], [0.5, 0.5], [0.25, 0.62]],
  "7": [[0.2, 0.12], [0.85, 0.12], [0.45, 0.92]],
  "8": [[0.5, 0.5], [0.25, 0.35], [0.4, 0.1], [0.65, 0.12], [0.75, 0.35], [0.5, 0.5], [0.22, 0.7], [0.35, 0.92], [0.65, 0.92], [0.78, 0.7], [0.5, 0.5]],
  "9": [[0.75, 0.38], [0.5, 0.5], [0.25, 0.38], [0.3, 0.14], [0.6, 0.1], [0.78, 0.3], [0.75, 0.55], [0.6, 0.92]],
  "/": [[0.75, 0.1], [0.25, 0.92]],
  "x": [[0.2, 0.2], [0.8, 0.8], [0.8, 0.2], [0.2, 0.8]]
};
/** Vẽ nhãn thành ảnh xám (nền ~240, nét tối). o: { size, jitter, thick, noise } */
function render(label, rng, o) {
  o = o || {}; const W = o.w || 48, H = o.h || 64, jit = o.jitter == null ? 0.05 : o.jitter, thick = (o.thick || 2.6) * (0.8 + 0.5 * rng());
  const g = new Uint8Array(W * H).fill(240);
  const ang = (rng() - 0.5) * 0.35, sx = 0.75 + 0.3 * rng(), sy = 0.8 + 0.2 * rng(), ox = (rng() - 0.5) * 6, oy = (rng() - 0.5) * 6;
  const pts = (P[label] || P["1"]).map(([x, y]) => { let X = (x - 0.5 + (rng() - 0.5) * jit) * sx, Y = (y - 0.5 + (rng() - 0.5) * jit) * sy; const c = Math.cos(ang), s = Math.sin(ang); return [W / 2 + ox + (X * c - Y * s) * W * 0.8, H / 2 + oy + (X * s + Y * c) * H * 0.8]; });
  const dot = (cx, cy) => { for (let y = Math.floor(cy - thick); y <= Math.ceil(cy + thick); y++) for (let x = Math.floor(cx - thick); x <= Math.ceil(cx + thick); x++) if (x >= 0 && y >= 0 && x < W && y < H && (x - cx) ** 2 + (y - cy) ** 2 <= thick * thick) g[y * W + x] = 30 + Math.floor(rng() * 40); };
  for (let i = 0; i + 1 < pts.length; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 2); for (let k = 0; k <= n; k++) dot(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n); }
  const nz = o.noise == null ? 6 : o.noise; if (nz) for (let i = 0; i < g.length; i++) g[i] = Math.max(0, Math.min(255, g[i] + Math.round((rng() - 0.5) * nz * 2)));
  return { g, w: W, h: H };
}
module.exports = { prng, render, LABELS: Object.keys(P) };
