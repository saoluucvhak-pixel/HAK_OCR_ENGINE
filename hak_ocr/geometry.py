"""Conservative planar perspective rectification with reversible viewing transform.
A curved page is NOT a planar quadrilateral; do not claim curved-dewarping here.
"""
from __future__ import annotations
import math
import cv2
import numpy as np
from PIL import Image


def order_quad(pts: np.ndarray) -> np.ndarray:
    points=np.asarray(pts,dtype='float32').reshape(4,2)
    center=points.mean(axis=0)
    angles=np.arctan2(points[:,1]-center[1],points[:,0]-center[0])
    points=points[np.argsort(angles)]
    top=int(np.argmin(points.sum(axis=1)))
    return np.roll(points,-top,axis=0)  # TL,TR,BR,BL


def detect_page_corners(image: Image.Image) -> list[list[float]] | None:
    rgb=np.asarray(image.convert('RGB'))
    h,w=rgb.shape[:2]
    if min(w,h)<160:return None
    factor=min(1.0,1250/max(w,h))
    small=cv2.resize(rgb,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(5,5),0)
    edge=cv2.Canny(gray,45,135)
    contours,_=cv2.findContours(edge,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    total=small.shape[0]*small.shape[1]
    candidates=[]
    for c in sorted(contours,key=cv2.contourArea,reverse=True)[:24]:
        a=cv2.contourArea(c)
        if not 0.25*total<a<0.97*total:continue
        per=cv2.arcLength(c,True)
        poly=cv2.approxPolyDP(c,0.022*per,True)
        if len(poly)!=4 or not cv2.isContourConvex(poly):continue
        pts=order_quad(poly.reshape(4,2).astype('float32'))
        lengths=[np.linalg.norm(pts[(i+1)%4]-pts[i]) for i in range(4)]
        if min(lengths)<50:continue
        candidates.append((a,pts))
    if not candidates:return None
    pts=max(candidates,key=lambda x:x[0])[1] / factor
    # If already nearly exactly the full image, there is no benefit.
    corners_ref=np.array([[0,0],[w,0],[w,h],[0,h]],dtype=float)
    err=float(np.mean(np.linalg.norm(pts-corners_ref,axis=1))/max(w,h))
    if err<0.015:return None
    return pts.tolist()


def warp_page(image: Image.Image, corners: list[list[float]] | None = None, *,
              auto: bool = False,max_pixels:int=25_000_000) -> tuple[Image.Image,dict]:
    src=image.convert('RGB')
    w,h=src.size
    detected = detect_page_corners(src) if auto and corners is None else None
    pts=order_quad(corners) if corners is not None else (order_quad(detected) if detected is not None else None)
    if pts is None:return src,{'method':'none','original_size':[w,h],'output_size':[w,h]}
    if not np.isfinite(pts).all() or (pts<0).any() or (pts[:,0]>w).any() or (pts[:,1]>h).any():
        raise ValueError('Tọa độ góc trang nằm ngoài ảnh')
    sizes=[np.linalg.norm(pts[(i+1)%4]-pts[i]) for i in range(4)]
    out_w=max(1,int(max(sizes[0],sizes[2])));out_h=max(1,int(max(sizes[1],sizes[3])))
    if out_w<70 or out_h<70:raise ValueError('Vùng trang quá nhỏ')
    factor=min(1.0,math.sqrt(max_pixels/(out_w*out_h)))
    out_w=int(out_w*factor);out_h=int(out_h*factor)
    target=np.array([[0,0],[out_w-1,0],[out_w-1,out_h-1],[0,out_h-1]],dtype='float32')
    matrix=cv2.getPerspectiveTransform(pts.astype('float32'),target)
    result=cv2.warpPerspective(np.asarray(src),matrix,(out_w,out_h),
                               flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
    return Image.fromarray(result),{'method':'perspective-quad','original_size':[w,h],
                                     'output_size':[out_w,out_h],
                                     'corners':pts.tolist()}


def reapply_geometry(image: Image.Image, info: dict) -> Image.Image:
    if not info or info.get('method')!='perspective-quad':return image
    original_w,original_h=info['original_size']
    ratio_x=image.width/original_w; ratio_y=image.height/original_h
    corners=[[p[0]*ratio_x,p[1]*ratio_y] for p in info['corners']]
    return warp_page(image,corners=corners)[0]
