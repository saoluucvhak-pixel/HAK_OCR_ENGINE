"""Conservative OCR candidates for small numeric cells in scanned grids.

Source pixels are never modified. Predictions are unverified until reviewed.
"""
from __future__ import annotations
import re
from PIL import Image, ImageOps
import cv2
import numpy as np
import pytesseract
from .validation import fold_vietnamese


def _normalize_numeric(value: str) -> str:
    value=value.strip().replace(' ','').replace('\n','')
    return value if re.fullmatch(r'(?:\d{1,3})(?:[.,]\d{1,2})?',value) else ''


def _prepare_digit_crop(region: Image.Image) -> tuple[Image.Image, float]:
    gray=np.array(ImageOps.grayscale(region))
    h,w=gray.shape
    # For day/attendance columns, the printed value is usually near the centre.
    # Narrowing also keeps long grid rules away from OCR text.
    if w>=75:
        side=int(w*.19)
        gray=gray[:,side:w-side]
    gray=cv2.GaussianBlur(gray,(3,3),0)
    _,bw=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    h,w=bw.shape
    # Remove clearly horizontal/diagonal line segments, never short characters.
    lines=cv2.HoughLinesP(bw,1,np.pi/180,threshold=max(14,w//4),
                          minLineLength=max(28,int(w*.52)),maxLineGap=9)
    if lines is not None:
        for ln in lines[:,0]:
            x0,y0,x1,y1=[int(v) for v in ln]
            if abs(y1-y0)<=max(3,abs(x1-x0)*.15):
                cv2.line(bw,(x0,y0),(x1,y1),0,3)
    # Thin long horizontal components are almost certainly residual rules.
    count,labels,stats,_=cv2.connectedComponentsWithStats(bw,8)
    cleaned=np.zeros_like(bw)
    for i in range(1,count):
        x,y,cw,ch,area=[int(z) for z in stats[i]]
        if area<3 or (cw>w*.5 and cw>ch*3):continue
        if ch<2 or (cw>ch*6 and cw>20):continue
        cleaned[labels==i]=255
    density=float(np.count_nonzero(cleaned))/max(cleaned.size,1)
    if density<0.002 or density>.32:return Image.new('L',(32,32),'white'),density
    # Generous white margin prevents Tesseract from clipping very thin '1'.
    scale=max(3,min(8,int(125/max(1,h))))
    big=cv2.resize(cleaned,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    out=cv2.copyMakeBorder(255-big,26,26,35,35,cv2.BORDER_CONSTANT,value=255)
    return Image.fromarray(out),density


def _single_stem_candidate(prepared: Image.Image) -> bool:
    """Flag a clear isolated narrow `1` in a numeric-only table cell.

    A slender stroke could also be 'I' or 'l' in general text.  This heuristic
    is therefore only available to *numeric table review*, never full OCR.
    It is a suggestion, not evidence that someone actually attended work.
    """
    a=np.asarray(prepared.convert('L')) < 110
    h,w=a.shape
    if not a.any(): return False
    n,_,stats,_=cv2.connectedComponentsWithStats(a.astype('uint8'),8)
    components=[]
    for x,y,cw,ch,area in stats[1:]:
        if area < 8:continue
        components.append((int(x),int(y),int(cw),int(ch),int(area)))
    if components:
        largest=max(v[4] for v in components)
        # A clipped border or dust mark far from the number is not a digit.
        # Keep punctuation next to the glyph so '1.5' is never simplified.
        components=[v for v in components if not (
            v[4] < largest*.20 and (v[0]+v[2]/2 < w*.24 or v[0]+v[2]/2 > w*.76))]
    if len(components)!=1:return False
    x,y,cw,ch,area=components[0]
    # Ignore rule remnants near cell boundaries and tiny dust blobs.
    if not (h*.24 <= ch <= h*.75 and 0.07 <= cw/max(ch,1) <= .38):return False
    if not (w*.28 <= x+cw/2 <= w*.72 and h*.20 <= y+ch/2 <= h*.80):return False
    if not (.05 <= area/max(cw*ch,1) <= .85):return False
    return True


def _tight_crop(prepared: Image.Image) -> Image.Image:
    arr=np.asarray(prepared.convert('L'))
    ys,xs=np.where(arr < 125)
    if not len(xs):return prepared
    x0,x1=max(0,int(xs.min())-3),min(arr.shape[1],int(xs.max())+4)
    y0,y1=max(0,int(ys.min())-3),min(arr.shape[0],int(ys.max())+4)
    return Image.fromarray(cv2.copyMakeBorder(arr[y0:y1,x0:x1],18,18,18,18,cv2.BORDER_CONSTANT,value=255))


def _read_number_detailed(region: Image.Image, lang: str='eng') -> dict | None:
    if region.width<8 or region.height<8:return None
    prepared,density=_prepare_digit_crop(region)
    if density<.002 or density>.32:return None
    if _single_stem_candidate(prepared):
        return {'value':'1','method':'numeric-stem-cv','confidence':'candidate'}
    whitelist='-c tessedit_char_whitelist=0123456789.,'
    votes=[]
    for sample,psm in ((prepared,10),(prepared,7),(_tight_crop(prepared),8)):
        try:
            raw=pytesseract.image_to_string(sample,lang=lang,
                        config=f'--psm {psm} --oem 1 {whitelist}',timeout=3)
            candidate=_normalize_numeric(raw)
            if candidate:votes.append(candidate)
        except Exception:
            continue
    if not votes:return None
    # Conflicting model responses are NOT silently resolved by picking first.
    if len(set(votes))>1:return None
    return {'value':votes[0], 'method':'tesseract-numeric',
            'confidence':'multi-pass' if len(votes)>1 else 'candidate'}


def _read_number(region: Image.Image, lang: str='eng') -> str:
    """Backward-compatible interface; never interprets blank as zero."""
    detail=_read_number_detailed(region,lang)
    return detail['value'] if detail else ''


def refine_numeric_tables(im: Image.Image,tables:list,*,limit:int=180) -> dict:
    """OCR numeric-looking cells with cell-level source references.

    Existing recognized numbers are left unchanged. Non-empty but ambiguous
    values are NEVER discarded. Blank still differs from zero.
    """
    budget=limit;proposed=0;attempted=0
    for table in tables:
        suggestions=[]
        for ri,row in enumerate(table.grid):
            for ci,value in enumerate(row):
                if budget<=0:break
                raw=str(value).strip()
                if re.fullmatch(r'\d+(?:[.,]\d+)?',raw):continue
                if raw not in ('','|','I','l','_','-'):continue
                bb=table.cell_boxes[ri][ci]
                x0=int(bb[0]*im.width);x1=int(bb[2]*im.width)
                y0=int(bb[1]*im.height);y1=int(bb[3]*im.height)
                cw=x1-x0;ch=y1-y0
                if min(cw,ch)<10 or ch>160 or cw>650:continue
                inset_x=min(8,max(3,int(cw*.015)))
                inset_y=max(2,min(8,int(ch*.06)))
                if cw<=2*inset_x or ch<=2*inset_y:continue
                crop=im.crop((x0+inset_x,y0+inset_y,x1-inset_x,y1-inset_y))
                budget-=1;attempted+=1
                candidate=_read_number_detailed(crop)
                if candidate:
                    # OCR output is presented in the unverified grid for fast
                    # review, but the suggestion is explicitly tagged.
                    table.grid[ri][ci]=candidate['value'];proposed+=1
                    suggestions.append({'row':ri,'col':ci,'value':candidate['value'],
                                        'method':candidate['method'],
                                        'confidence':candidate['confidence'],
                                        'verified':False,'bbox':bb})
            if budget<=0:break
        table.cell_suggestions=suggestions
    return {'attempted':attempted,'filled':proposed,'limit':limit,
            'status':'unverified OCR candidates; user review mandatory'}


def refine_attendance_headers(im: Image.Image, tables: list, lang: str='vie+eng') -> int:
    """Recover supported attendance column labels when full-page OCR misses.

    Never guesses missing labels from the *position* of a column.  Only
    inserts a label actually read from the header pixels by two OCR passes.
    """
    known={'ngay':'Ngày','cong':'CÔNG','com':'CƠM',
           'ho va ten':'HỌ VÀ TÊN','tong cong':'Tổng công','tong com':'Tổng cơm'}
    found=0
    for table in tables:
        if not table.grid:continue
        for ci,value in enumerate(table.grid[0]):
            if str(value).strip():continue
            bb=table.cell_boxes[0][ci]
            x0,y0,x1,y1=[int(v*s) for v,s in zip(bb,(im.width,im.height,im.width,im.height))]
            if x1-x0<75 or y1-y0<19:continue
            for dx,dy in ((8,6),(6,5)):
                if x1-x0<2*dx+12 or y1-y0<2*dy+12:continue
                crop=im.crop((x0+dx,y0+dy,x1-dx,y1-dy))
                votes=[]
                for psm in (6,7):
                    try:
                        content=pytesseract.image_to_string(crop,lang=lang,
                                        config=f'--psm {psm} --oem 1',timeout=3)
                        key=re.sub(r'[^a-z ]','',fold_vietnamese(content)).strip()
                        key=' '.join(key.split())
                        votes.append(known.get(key))
                    except Exception:
                        votes.append(None)
                if votes[0] and votes[0]==votes[1]:
                    table.grid[0][ci]=votes[0]
                    table.cell_suggestions.append({'row':0,'col':ci,'value':votes[0],
                        'method':'header-two-pass-ocr','confidence':'multi-pass',
                        'verified':False,'bbox':bb})
                    found+=1
                    break
    return found
