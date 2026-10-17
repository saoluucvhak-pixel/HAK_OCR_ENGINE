"""V3 perspective rectification: explicit corner geometry, no silent auto-correction.

Coordinates are on the EXIF-oriented source image. Caller must confirm corners.
The original is never modified and output is always a separate file.
"""
from pathlib import Path
from math import hypot, isfinite

def _ordered(corners):
    if len(corners) != 4 or any(len(p) != 2 for p in corners):
        raise ValueError("Exactly four [x,y] corners required")
    points = [(float(x),float(y)) for x,y in corners]
    if any(not isfinite(v) for point in points for v in point):
        raise ValueError("Non-finite corner coordinate")
    if len(set(points)) != 4:
        raise ValueError("Corners must be distinct")
    center = (sum(p[0] for p in points)/4,sum(p[1] for p in points)/4)
    from math import atan2
    points.sort(key=lambda p:atan2(p[1]-center[1],p[0]-center[0]))
    start=min(range(4),key=lambda i:points[i][0]+points[i][1])
    points=points[start:]+points[:start]
    # Top-left, top-right, bottom-right, bottom-left
    if points[1][0] < points[3][0]:
        points=[points[0],points[3],points[2],points[1]]
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
    turns=[cross(points[i],points[(i+1)%4],points[(i+2)%4]) for i in range(4)]
    if min(turns)<=0:
        raise ValueError("Corners must form a convex quadrilateral")
    return points

def rectify_document(source, destination, corners, *, max_pixels=24_000_000):
    """Warp a manually confirmed quadrilateral to an upright rectangular copy."""
    try:
        import cv2
        import numpy as np
        from PIL import Image,ImageOps
    except ImportError as exc:
        raise RuntimeError("Requires opencv-python, numpy and Pillow") from exc
    src=Path(source).resolve(strict=True)
    dst=Path(destination).resolve()
    if src==dst:
        raise ValueError("Refusing to overwrite source")
    ordered=_ordered(corners)
    with Image.open(src) as image:
        rgb=np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    height,width=rgb.shape[:2]
    if any(x<0 or y<0 or x>=width or y>=height for x,y in ordered):
        raise ValueError("Corners outside source image")
    tl,tr,br,bl=ordered
    out_w=round(max(hypot(tr[0]-tl[0],tr[1]-tl[1]),hypot(br[0]-bl[0],br[1]-bl[1])))
    out_h=round(max(hypot(bl[0]-tl[0],bl[1]-tl[1]),hypot(br[0]-tr[0],br[1]-tr[1])))
    if out_w<10 or out_h<10 or out_w*out_h>max_pixels:
        raise ValueError("Rectified output dimensions outside limits")
    target=np.float32([[0,0],[out_w-1,0],[out_w-1,out_h-1],[0,out_h-1]])
    matrix=cv2.getPerspectiveTransform(np.float32(ordered),target)
    corrected=cv2.warpPerspective(rgb,matrix,(out_w,out_h),
                                   flags=cv2.INTER_CUBIC,borderValue=(255,255,255))
    dst.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(corrected).save(dst)
    return {"image":str(dst),"width":out_w,"height":out_h,
            "source_corners":[list(p) for p in ordered],
            "geometry_verified":False,"status":"NEEDS_REVIEW"}
