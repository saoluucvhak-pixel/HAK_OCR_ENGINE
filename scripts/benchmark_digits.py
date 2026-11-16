"""Synthetic benchmark for per-cell numeric OCR (deep_cells).

Renders attendance-style numeric cells with KNOWN values (1, 0.5, 2, 10, ...)
at several font sizes, small rotations, blur and noise, then runs the same
reader used by the app. Ground truth is exact by construction.

Reports, per condition:
  - correct:    prediction == truth
  - abstained:  reader returned nothing (safe: a human must read the cell)
  - WRONG:      prediction != truth and not empty (dangerous: a confident error)

Synthetic images are NOT real scans. Use this to compare code changes,
not to claim accuracy on HAK documents.

Run from project root:  python scripts/benchmark_digits.py [--seed 1] [--json]
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hak_ocr.deep_cells import _read_number_detailed  # noqa: E402

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
VALUES = ['1', '0.5', '0', '2', '10', '1.5', '8', '4', '0.5', '12']
SIZES = [18, 22, 26, 32]          # font pixel sizes ~ scanned cell heights
CONDITIONS = {
    'clean':      dict(rot=0.0, blur=0.0, noise=0),
    'slight-rot': dict(rot=1.5, blur=0.0, noise=0),
    'blur':       dict(rot=0.0, blur=1.0, noise=0),
    'noisy':      dict(rot=0.0, blur=0.6, noise=18),
}


def render_cell(value: str, size: int, cond: dict, rng: random.Random) -> Image.Image:
    cw, ch = 90, 60
    im = Image.new('L', (cw, ch), 255)
    d = ImageDraw.Draw(im)
    # Grid rules like a printed attendance table.
    d.rectangle([0, 0, cw - 1, ch - 1], outline=0, width=2)
    font = ImageFont.truetype(FONT, size)
    bx = d.textbbox((0, 0), value, font=font)
    tw, th = bx[2] - bx[0], bx[3] - bx[1]
    d.text(((cw - tw) / 2 - bx[0], (ch - th) / 2 - bx[1]), value, font=font, fill=0)
    if cond['rot']:
        im = im.rotate(rng.uniform(-cond['rot'], cond['rot']), fillcolor=255, expand=False)
    if cond['blur']:
        im = im.filter(ImageFilter.GaussianBlur(cond['blur']))
    if cond['noise']:
        px = im.load()
        for _ in range(cw * ch // 25):
            x, y = rng.randrange(cw), rng.randrange(ch)
            px[x, y] = max(0, min(255, px[x, y] + rng.randint(-cond['noise'], cond['noise'])))
    return im


def run(seed: int) -> dict:
    rng = random.Random(seed)
    results = {}
    for name, cond in CONDITIONS.items():
        stats = {'total': 0, 'correct': 0, 'abstained': 0, 'wrong': 0, 'wrong_examples': []}
        for value in VALUES:
            for size in SIZES:
                img = render_cell(value, size, cond, rng)
                detail = _read_number_detailed(img, 'eng')
                predicted = detail['value'] if detail else ''
                stats['total'] += 1
                if predicted == value:
                    stats['correct'] += 1
                elif predicted == '':
                    stats['abstained'] += 1
                else:
                    stats['wrong'] += 1
                    if len(stats['wrong_examples']) < 5:
                        stats['wrong_examples'].append({'truth': value, 'size': size, 'predicted': predicted})
        results[name] = stats
    return results


def summarize(results: dict) -> dict:
    rows = {k: v for k, v in results.items() if not k.startswith('_')}
    total = sum(v['total'] for v in rows.values())
    return {
        'seed_note': 'synthetic cells; exact ground truth',
        'total': total,
        'correct': sum(v['correct'] for v in rows.values()),
        'abstained': sum(v['abstained'] for v in rows.values()),
        'wrong': sum(v['wrong'] for v in rows.values()),
        'by_condition': rows,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--json', action='store_true')
    args = p.parse_args()
    summary = summarize(run(args.seed))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"total={summary['total']} correct={summary['correct']} "
          f"abstained={summary['abstained']} WRONG={summary['wrong']}")
    for name, s in summary['by_condition'].items():
        print(f"  {name:11s} correct {s['correct']:3d}/{s['total']}  abstained {s['abstained']:3d}  WRONG {s['wrong']:3d}  {s['wrong_examples'] if s['wrong'] else ''}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
