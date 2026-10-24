"""Offline OpenCV candidate document quadrilateral detector.

All output is advisory: source corner positions must be reviewed before warping.
"""
from pathlib import Path
from .perspective import _ordered

def detect_document_corners(source, *, min_area_ratio=.12, max_pixels=18_000_000):
    if not 0 < min_area_ratio < 1:
        raise ValueError("min_area_ratio must be between 0 and 1")
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Requires OpenCV, numpy and Pillow") from exc
    with Image.open(Path(source)) as image:
        rgb=np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    height,width=rgb.shape[:2]
    if height*width>max_pixels:
        raise ValueError("Image too large for corner detection")
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    blurred=cv2.GaussianBlur(gray,(5,5),0)
    edges=cv2.Canny(blurred,45,135)
    edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for contour in contours:
        perimeter=cv2.arcLength(contour,True)
        if perimeter<=0:
            continue
        approx=cv2.approxPolyDP(contour,.025*perimeter,True)
        if len(approx)!=4 or not cv2.isContourConvex(approx):
            continue
        area=abs(cv2.contourArea(approx))
        if area<width*height*min_area_ratio:
            continue
        try:
            ordered=_ordered(approx.reshape(4,2).tolist())
        except ValueError:
            continue
        candidates.append((area,ordered))
    candidates.sort(key=lambda x:x[0],reverse=True)
    if not candidates:
        return {"found":False,"corners":None,"verified":False,
                "status":"NEEDS_REVIEW","warnings":["CORNERS_NOT_FOUND"]}
    area,points=candidates[0]
    return {"found":True,"corners":[list(p) for p in points],
            "area_ratio":round(area/(width*height),4),
            "verified":False,"status":"NEEDS_REVIEW",
            "warnings":["CORNERS_REQUIRE_MANUAL_CONFIRMATION"]}
