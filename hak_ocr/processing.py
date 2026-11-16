from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import uuid
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageSequence
import pytesseract
from pytesseract import Output

from .engine_config import setup_tesseract
from .models import Block, Field, Page, Result, Table
from .validation import fold_vietnamese, validate_attendance_grid
from .templates import DEFAULT_ATTENDANCE_TEMPLATE, extract_template_fields
from .deep_cells import refine_numeric_tables, refine_attendance_headers
from .grid_refinement import refine_regular_lines
from .advanced_engines import PaddleLocal, merge_ocr_candidates, extract_docling
from .geometry import warp_page, reapply_geometry

Image.MAX_IMAGE_PIXELS = 100_000_000


def available_languages() -> set[str]:
    setup_tesseract()
    try:
        return set(pytesseract.get_languages(config=''))
    except (OSError,pytesseract.TesseractNotFoundError):
        return set()


def check_ocr_ready() -> str:
    langs = available_languages()
    if 'vie' not in langs:
        raise RuntimeError('Chưa có Tesseract hoặc gói ngôn ngữ vie.traineddata (cần cài/đóng gói offline).')
    return 'vie+eng' if 'eng' in langs else 'vie'


def clamp(v: float):
    return max(0.0, min(1.0, float(v)))


def normalize_bbox(x0,y0,x1,y1,w,h):
    return [clamp(x0 / w),clamp(y0 / h),clamp(x1 / w),clamp(y1 / h)]


def image_array(im: Image.Image) -> np.ndarray:
    return np.array(im.convert('RGB'))


def rotate_degrees(im: Image.Image, angle: int) -> Image.Image:
    return im.rotate(angle,expand=True) if angle else im


def choose_orientation(im: Image.Image, lang: str, detect: bool = True) -> int:
    if not detect:
        return 0
    thumb=im.copy().convert('RGB')
    thumb.thumbnail((1450,1450))
    try:
        raw=pytesseract.image_to_osd(thumb,output_type=Output.DICT,config='--psm 0')
        angle=int(raw.get('rotate',0))
        # Tesseract's rotate is CLOCKWISE; Pillow rotates COUNTERCLOCKWISE.
        # For a clockwise correction angle, Pillow.rotate(-angle).
        if float(raw.get('orientation_conf',0)) >= 2.0:
            return (-angle)%360
    except Exception:
        pass
    # Fallback only when markedly better; OCR small thumbnails in 4 orientations.
    scores=[]
    for angle in (0,90,180,270):
        sample=rotate_degrees(thumb,angle)
        try:
            data=pytesseract.image_to_data(sample,lang=lang,output_type=Output.DICT,config='--psm 11')
            words=[(str(t).strip(),float(c)) for t,c in zip(data['text'],data['conf'])
                   if str(t).strip() and float(c)>=20]
            score=sum(max(0,c) * min(len(t),18) for t,c in words)
        except Exception:
            score=0
        scores.append((score,angle))
    scores.sort(reverse=True)
    best,angle=scores[0]
    baseline=next(s for s,a in scores if a==0)
    return angle if best > max(100,baseline*1.5) else 0


def enhance_image(im: Image.Image) -> Image.Image:
    # Preserve tonal information; avoid adaptive threshold as a global default.
    array=np.array(im.convert('RGB'))
    gray=cv2.cvtColor(array,cv2.COLOR_RGB2GRAY)
    clahe=cv2.createCLAHE(clipLimit=1.7,tileGridSize=(8,8))
    enhanced=clahe.apply(gray)
    return Image.fromarray(enhanced)


def recognize_words(im: Image.Image, lang: str) -> list[Block]:
    data=pytesseract.image_to_data(im,lang=lang,output_type=Output.DICT,config='--psm 11 --oem 1')
    w,h=im.size
    words=[]
    for i,text in enumerate(data['text']):
        content=str(text).strip()
        if not content: continue
        try: confidence=float(data['conf'][i])
        except (ValueError,TypeError):confidence=-1
        if confidence < 0: continue
        x,y=int(data['left'][i]),int(data['top'][i]); width,height=int(data['width'][i]),int(data['height'][i])
        words.append(Block(content,normalize_bbox(x,y,x+width,y+height,w,h),confidence,'tesseract',0))
    return words


def blocks_to_text(blocks: list[Block]) -> str:
    if not blocks:return ''
    # Row grouping with word-height adaptive tolerance.
    ordered=sorted(blocks,key=lambda b:((b.bbox[1]+b.bbox[3])/2,b.bbox[0]))
    row_height=max(0.006,float(np.median([b.bbox[3]-b.bbox[1] for b in ordered])))
    lines=[]
    for b in ordered:
        mid=(b.bbox[1]+b.bbox[3])/2
        if lines and abs(mid-lines[-1][0])<=row_height*0.7:
            lines[-1][1].append(b)
            lines[-1]=(sum((v.bbox[1]+v.bbox[3])/2 for v in lines[-1][1])/len(lines[-1][1]),lines[-1][1])
        else:lines.append((mid,[b]))
    return '\n'.join(' '.join(b.text for b in sorted(line,key=lambda b:b.bbox[0])) for _,line in lines)


def _line_centers(mask: np.ndarray, axis: str, min_span: int) -> list[int]:
    binary=(mask>0).sum(axis=1 if axis=='horizontal' else 0)
    positions=np.flatnonzero(binary>min_span)
    groups=[]
    for p in positions:
        if not groups or p>groups[-1][-1]+2:groups.append([int(p)])
        else:groups[-1].append(int(p))
    return [int(np.median(g)) for g in groups if len(g)<50]


def detect_table(im: Image.Image, words: list[Block], page_number: int, max_cells: int = 3500) -> list[Table]:
    """Grid-ruled table detector. Reject weak grids instead of inventing cells."""
    raw=image_array(im)
    h,w=raw.shape[:2]
    if h<100 or w<100:return []
    gray=cv2.cvtColor(raw,cv2.COLOR_RGB2GRAY)
    blur=cv2.GaussianBlur(gray,(3,3),0)
    binary=cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY_INV,31,13)
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,max(24,w//48)),np.uint8))
    vertical=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((max(24,h//38),1),np.uint8))
    # Table extraction limited to prominent grids; handwritten/non-ruled data
    # remains ordinary OCR text for manual review.
    cols=_line_centers(vertical,'vertical',int(h*0.05))
    rows=_line_centers(horizontal,'horizontal',int(w*0.05))
    # Perspective/noisy thin rules can appear as several closely spaced
    # horizontal positions. Retain the most consistent ruled intervals when
    # there are enough rows to justify the reconstruction.
    rows, axis_report=refine_regular_lines(rows,min_lines=20)
    if len(rows)<3 or len(cols)<3:return []
    if (len(rows)-1)*(len(cols)-1)>max_cells:return []
    # Remove far apart lines (usually page boundaries) by using broad shared span.
    tables=[]
    b=normalize_bbox(cols[0],rows[0],cols[-1],rows[-1],w,h)
    if (b[2]-b[0])<.25 or (b[3]-b[1])<.09:return []
    table_grid=[];cell_boxes=[]
    for ri in range(len(rows)-1):
        row_values=[];row_boxes=[]
        for ci in range(len(cols)-1):
            x0,x1=cols[ci],cols[ci+1];y0,y1=rows[ri],rows[ri+1]
            cb=normalize_bbox(x0,y0,x1,y1,w,h)
            row_boxes.append(cb)
            matches=[v for v in words if x0/w <= (v.bbox[0]+v.bbox[2])/2 <= x1/w
                     and y0/h <= (v.bbox[1]+v.bbox[3])/2 <= y1/h]
            matches.sort(key=lambda b:((b.bbox[1]+b.bbox[3])/2,b.bbox[0]))
            row_values.append(' '.join(v.text for v in matches))
        table_grid.append(row_values);cell_boxes.append(row_boxes)
    stable=f'page-{page_number}-grid-1'
    tables.append(Table(page_number,b,table_grid,cell_boxes,
                        'opencv-grid-v2-refined' if axis_report.get('changed') else 'opencv-grid-v1',stable))
    return tables


def _native_pdf_blocks(page, page_index: int) -> list[Block]:
    import fitz
    words=page.get_text('words',sort=True)
    w=float(page.rect.width);h=float(page.rect.height)
    return [Block(str(v[4]),normalize_bbox(v[0],v[1],v[2],v[3],w,h),None,'pdf-text',page_index) for v in words]


def _extract_single_page(im: Image.Image, n: int, lang: str, detect_rotation: bool,
                         table_mode: bool, orientation_override: int | None = None,
                         deep_cells: bool = False, ocr_engine: str = 'tesseract',
                         paddle=None, auto_perspective: bool = False) -> Page:
    im=ImageOps.exif_transpose(im).convert('RGB')
    orientation=orientation_override if orientation_override is not None else choose_orientation(im,lang,detect_rotation)
    im=rotate_degrees(im,orientation)
    geometry={}
    if auto_perspective:
        im,geometry=warp_page(im,auto=True)
    if im.width*im.height>40_000_000:
        ratio=math.sqrt(40_000_000/(im.width*im.height))
        im=im.resize((int(im.width*ratio),int(im.height*ratio)))
    alt=[]
    if ocr_engine == 'paddle':
        if paddle is None:raise RuntimeError('Chưa có PaddleOCR offline')
        blocks=paddle.recognize(im,page=n)
    elif ocr_engine == 'hybrid':
        if paddle is None:raise RuntimeError('Chưa có PaddleOCR offline')
        blocks,alt=merge_ocr_candidates(recognize_words(enhance_image(im),lang),paddle.recognize(im,page=n))
    else:
        blocks=recognize_words(enhance_image(im),lang)
    for block in blocks:block.page=n
    tables=detect_table(im,blocks,n) if table_mode else []
    if deep_cells and tables:
        refine_numeric_tables(im,tables)
        refine_attendance_headers(im,tables,lang)
    p=Page(n,im.width,im.height,blocks_to_text(blocks),blocks,tables,orientation,
           'ocr-'+ocr_engine)
    p.geometry=geometry
    p.ocr_alternatives=alt
    if alt:p.warnings.append(f'{len(alt)} vùng OCR mâu thuẫn giữa các bộ máy; cần kiểm duyệt')
    return p


def detect_type(text: str) -> str:
    lower=fold_vietnamese(text)
    if any(s in lower for s in ('cham cong','bang cong','lich lam','cong xuat hang','van tay','xac nhan cong nhan vien cong tac')):
        return 'bang_cham_cong'
    if 'phieu can' in lower or 'khoi luong can' in lower:return 'phieu_can'
    if 'hoa don' in lower:return 'hoa_don'
    if 'hop dong' in lower:return 'hop_dong'
    if 'chuyen ung luong' in lower or 'uy nhiem chi' in lower:return 'ung_luong'
    return 'generic'


def extract_fields(pages: list[Page], doc_type: str) -> list[Field]:
    specs=[('ky','Kỳ tháng',r'(?:tháng\s*)(\d{1,2}\s*[/\\-]\s*20\d{2}|\d{1,2}\s+năm\s+20\d{2})'),
           ('tong_cong','Tổng công',r'(?:tổng\s*công|TC)\s*[:\s]+(\d+(?:[.,]\d+)?)'),
           ('tong_com','Tổng cơm',r'(?:tổng\s*cơm)\s*[:\s]+(\d+(?:[.,]\d+)?)'),
           ('so_chung_tu','Số chứng từ',r'(?:số\s*chứng\s*từ)\s*:?\s*([A-Z\d/-]+)'),
           ('so_tien','Số tiền',r'(?:số\s*tiền)\s*:?\s*([\d.,]+)')]
    out=[]
    for key,label,pattern in specs:
        for page in pages:
            m=re.search(pattern,page.text,re.IGNORECASE)
            if m:
                value=m.group(1).strip(); bbox=None; confidence=None
                # Match value word with best source positioning where possible.
                word=next((b for b in page.blocks if b.text.strip('.,:')==value.strip('.,:')),None)
                if word: bbox=word.bbox;confidence=word.confidence
                out.append(Field(key,label,value,value,page.number,bbox,confidence,False,'ocr'))
                break
    return out


def process_file(path: str | Path, doc_id: str, digest: str, *,
                 progress: Callable[[int,int],None] | None = None,
                 detect_rotation: bool = True, tables: bool = True,
                 custom_templates: list[dict] | None = None,
                 deep_cells: bool = False, force_type: str | None = None,
                 ocr_engine: str = 'tesseract', docling_enabled: bool = False,
                 auto_perspective: bool = False, models_dir: Path | None = None) -> Result:
    """Deterministic offline processing; no network calls, no auto-learning or changes to original."""
    source=Path(path)
    if ocr_engine not in ('tesseract','paddle','hybrid'):
        raise ValueError('OCR engine phải là tesseract, paddle hoặc hybrid')
    lang=check_ocr_ready() if ocr_engine in ('tesseract','hybrid') or detect_rotation or deep_cells else 'vie'
    paddle=PaddleLocal(base=models_dir) if ocr_engine in ('paddle','hybrid') else None
    pages=[]; warnings=[]; layout={}
    if docling_enabled:
        layout=extract_docling(source,base=models_dir)

    if source.suffix.lower()=='.pdf':
        import fitz
        with fitz.open(str(source)) as doc:
            if doc.needs_pass:raise ValueError('PDF có mật khẩu; bản đầu tiên chưa hỗ trợ mở mật khẩu')
            if len(doc)>200: raise ValueError('PDF hơn 200 trang: cần chia tệp')
            for i,page in enumerate(doc):
                native=_native_pdf_blocks(page,i)
                usable=len(native)>=12 and sum(len(b.text) for b in native)>=60
                # Render on demand. Cap scale to prevent gigantic pages.
                zoom=min(2.35,math.sqrt(30_000_000/max(1,page.rect.width*page.rect.height)))
                pix=page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False)
                im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                if usable:
                    if any(v=='\ufffd' for v in ''.join(b.text for b in native)):
                        warnings.append(f'Trang {i+1}: lớp chữ chứa ký tự lỗi, cần review')
                    detected=detect_table(im,native,i) if tables else []
                    p=Page(i,im.width,im.height,blocks_to_text(native),native,detected,0,'pdf-text')
                else:
                    p=_extract_single_page(im,i,lang,detect_rotation,tables,deep_cells=deep_cells,ocr_engine=ocr_engine,paddle=paddle,auto_perspective=auto_perspective)
                pages.append(p)
                if progress: progress(i+1,len(doc))
    else:
        with Image.open(source) as image:
            frames=getattr(image,'n_frames',1)
            if frames>200:raise ValueError('Ảnh TIFF quá 200 trang')
            for i in range(frames):
                image.seek(i)
                pages.append(_extract_single_page(image.copy(),i,lang,detect_rotation,tables,deep_cells=deep_cells,ocr_engine=ocr_engine,paddle=paddle,auto_perspective=auto_perspective))
                if progress:progress(i+1,frames)
    full_text='\n'.join(p.text for p in pages)
    typ=force_type if force_type and force_type!='generic' else detect_type(full_text)
    fields=extract_fields(pages,typ)
    template_fields=extract_template_fields(pages,[DEFAULT_ATTENDANCE_TEMPLATE]+(custom_templates or []),typ)
    seen={f.key for f in fields}
    fields.extend(f for f in template_fields if f.key not in seen)
    if typ=='bang_cham_cong':
        for page in pages:
            for table in page.tables:
                warnings.extend('Trang '+str(page.number+1)+': '+issue['message'] for issue in validate_attendance_grid(table.grid))
    warnings.extend(w for page in pages for w in page.warnings)
    result=Result(doc_id,digest,source.name,typ,pages,fields,warnings,'NEEDS_REVIEW',uuid.uuid4().hex)
    result.layout_extraction=layout
    return result


def render_preview(source: str | Path,page_num: int, orientation: int = 0, limit: int = 1800, geometry: dict | None = None) -> Image.Image:
    src=Path(source)
    if src.suffix.lower()=='.pdf':
        import fitz
        with fitz.open(str(src)) as doc:
            page=doc[page_num]
            pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False)
            im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    else:
        with Image.open(src) as image:
            image.seek(page_num)
            im=ImageOps.exif_transpose(image.copy()).convert('RGB')
    im=rotate_degrees(im,orientation)
    if geometry and geometry.get('method')=='perspective-quad':
        im=reapply_geometry(im,geometry)
    im.thumbnail((limit,limit))
    return im
