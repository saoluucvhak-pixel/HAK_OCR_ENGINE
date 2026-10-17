"""Optional OpenCV ruled-grid detector; returns candidates, never inferred payroll data."""
from pathlib import Path

def _clusters(points, gap=3):
    out = []
    for point in sorted(set(int(x) for x in points)):
        if not out or point - out[-1][-1] > gap:
            out.append([point])
        else:
            out[-1].append(point)
    return [round(sum(c) / len(c)) for c in out]

def detect_grid(image_path, *, min_cell_width=8, min_cell_height=8,
                threshold_fraction=0.45):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Grid detection requires opencv-python and numpy") from exc
    from PIL import Image, ImageOps
    with Image.open(Path(image_path)) as original:
        rgb = np.array(ImageOps.exif_transpose(original).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    if h < 40 or w < 40:
        raise ValueError("Image too small for grid detection")
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 12)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12,w//65),1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1,max(12,h//45)))
    h_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
    v_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
    x_count = np.count_nonzero(v_mask,axis=0)
    y_count = np.count_nonzero(h_mask,axis=1)
    xs = _clusters(np.flatnonzero(x_count >= h*threshold_fraction))
    ys = _clusters(np.flatnonzero(y_count >= w*threshold_fraction))
    xs = [x for i,x in enumerate(xs) if i==0 or x-xs[i-1]>=min_cell_width]
    ys = [y for i,y in enumerate(ys) if i==0 or y-ys[i-1]>=min_cell_height]
    return {"xs":xs,"ys":ys,"image_size":[w,h],
            "grid_found":len(xs)>=2 and len(ys)>=2,
            "verified":False,
            "warnings":[] if len(xs)>=2 and len(ys)>=2 else ["GRID_NOT_DETECTED"]}
