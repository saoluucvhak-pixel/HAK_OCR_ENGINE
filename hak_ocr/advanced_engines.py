"""Optional local-only PaddleOCR and Docling adapters.

A model directory is mandatory. No auto-download, silent switch to cloud APIs,
or implicit fallback is permitted. Importing this module never imports heavy ML libs.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
from typing import Any, Callable
import numpy as np
from PIL import Image
from .config import data_home, resource_root
from .models import Block


class OfflineModelError(RuntimeError):
    pass


def prevent_remote_model_resolution() -> None:
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    os.environ['DOCLING_ENABLE_REMOTE_SERVICES'] = 'false'


def model_root() -> Path:
    custom = os.environ.get('HAK_OCR_MODELS_DIR')
    return Path(custom).expanduser().resolve() if custom else (resource_root() / 'vendor' / 'models')


def required_model_dir(name: str, base: Path | None = None) -> Path:
    """Deliberately rejects missing/empty models BEFORE optional import/initialization."""
    base = (base or model_root()).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise OfflineModelError('Model phải nằm trong thư mục cấu hình cục bộ.')
    if not path.is_dir() or not any(path.iterdir()):
        raise OfflineModelError(f'Thiếu model offline: {path}. Hãy nhập gói model hợp lệ bằng phương tiện cục bộ.')
    return path


def engine_report(base: Path | None = None) -> dict:
    base = base or model_root()
    models = {k: (base / k).is_dir() and any((base / k).iterdir())
              for k in ('paddle_detection','paddle_recognition','docling','handwriting','doc_unwarp','evidence_llm','unlimited_ocr')}
    return {
        'model_root': str(base),
        'models': models,
        'libraries': {x: importlib.util.find_spec(x) is not None
                      for x in ('paddleocr','docling','transformers','torch')},
        'network_required': False,
    }


def _dict_result(obj: Any) -> dict:
    if isinstance(obj, dict):
        data = obj
    else:
        raw = getattr(obj, 'json', None)
        if callable(raw):
            raw = raw()
        if not isinstance(raw, dict):
            raise ValueError('PaddleOCR không trả về cấu trúc JSON được hỗ trợ')
        data = raw
    return data.get('res', data)


def paddle_result_to_blocks(results: list, width: int, height: int, page: int = 0) -> list[Block]:
    """Convert PaddleOCR 3.x rec_* fields to normalized source-linked rectangles."""
    blocks=[]
    for result in results:
        data=_dict_result(result)
        texts=data.get('rec_texts',[])
        scores=data.get('rec_scores',[])
        polys=data.get('rec_polys')
        boxes=data.get('rec_boxes')
        if polys is None and boxes is None:
            raise ValueError('PaddleOCR không có rec_polys/rec_boxes để truy vết nguồn')
        for i, text in enumerate(texts):
            if not str(text).strip():continue
            coords=np.asarray(polys[i] if polys is not None else boxes[i],dtype=float).reshape(-1,2) if polys is not None else None
            if coords is not None:
                x0,y0=coords.min(axis=0);x1,y1=coords.max(axis=0)
            else:
                x0,y0,x1,y1=map(float,boxes[i])
            box=[max(0.0,min(1.0,float(x0)/width)),max(0.0,min(1.0,float(y0)/height)),
                 max(0.0,min(1.0,float(x1)/width)),max(0.0,min(1.0,float(y1)/height))]
            if box[2]<=box[0] or box[3]<=box[1]:continue
            score=float(scores[i]) if i<len(scores) else 0.0
            blocks.append(Block(str(text),box,100*max(0.0,min(score,1.0)),'paddleocr-local',page,'line'))
    return blocks


class PaddleLocal:
    def __init__(self, base: Path | None = None, factory: Callable | None = None):
        prevent_remote_model_resolution()
        det=required_model_dir('paddle_detection',base)
        rec=required_model_dir('paddle_recognition',base)
        if factory is None:
            try:from paddleocr import PaddleOCR
            except ImportError as e:raise OfflineModelError('Chưa cài paddleocr/paddlepaddle từ wheel offline') from e
            factory=PaddleOCR
        # Explicitly disable modules whose default configuration would fetch extra models.
        self.pipeline=factory(text_detection_model_dir=str(det),text_recognition_model_dir=str(rec),
                              use_doc_orientation_classify=False,use_doc_unwarping=False,
                              use_textline_orientation=False)

    def recognize(self, image: Image.Image, page: int = 0) -> list[Block]:
        arr=np.asarray(image.convert('RGB'))
        results=self.pipeline.predict(arr)
        return paddle_result_to_blocks(list(results),image.width,image.height,page)


def _iou(a:list[float],b:list[float]) -> float:
    x0=max(a[0],b[0]);y0=max(a[1],b[1]);x1=min(a[2],b[2]);y1=min(a[3],b[3])
    inner=max(0,x1-x0)*max(0,y1-y0)
    aa=(a[2]-a[0])*(a[3]-a[1]);bb=(b[2]-b[0])*(b[3]-b[1])
    return inner/max(aa+bb-inner,1e-9)


def merge_ocr_candidates(tesseract: list[Block], paddle: list[Block]) -> tuple[list[Block],list[dict]]:
    """Non-destructive arbitration across Tesseract word/Paddle line granularity.

    A line-level result may cover several Tesseract words. In such a case it is
    evidence, NOT an additional text line; adding both duplicates extracted text.
    """
    merged=list(tesseract);alternatives=[]
    for p in paddle:
        x0,y0,x1,y1=p.bbox
        area=max((x1-x0)*(y1-y0),1e-9)
        overlaps=[]
        for idx,t in enumerate(tesseract):
            a,b,c,d=t.bbox
            intersection=max(0,min(x1,c)-max(x0,a))*max(0,min(y1,d)-max(y0,b))
            if intersection/max((c-a)*(d-b),1e-9)>0.65:
                overlaps.append((idx,intersection))
        coverage=sum(inter for _,inter in overlaps)/area
        if not overlaps or coverage<0.22:
            merged.append(p)
            continue
        ts=[tesseract[idx] for idx,_ in sorted(overlaps,key=lambda item:tesseract[item[0]].bbox[0])]
        combined=' '.join(t.text for t in ts).strip()
        if combined.casefold()!=p.text.casefold().strip():
            alternatives.append({'bbox':p.bbox,'tesseract':combined,'paddle':p.text,
                                 'tesseract_confidence':sum((t.confidence or 0) for t in ts)/len(ts),
                                 'paddle_confidence':p.confidence,'status':'NEEDS_REVIEW'})
        # Even if Paddle confidence is higher, keep the existing Tesseract words
        # to retain stable downstream field extraction and cell provenance.
    return merged,alternatives


def extract_docling(source: Path, *, base: Path | None = None, converter_factory=None,
                    use_local_tesseract: bool = False) -> dict:
    """Run Docling locally as *supplementary* layout/text interpretation.
    Markdown does NOT provide precise clickable bbox; never override OCR's reviewed cells.
    """
    if source.suffix.lower()!='.pdf':
        return {'status':'SKIPPED','reason':'Docling adapter 1.1.0 xử lý PDF'}
    prevent_remote_model_resolution()
    artifacts=required_model_dir('docling',base)
    if converter_factory is None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter,PdfFormatOption
            options=PdfPipelineOptions(artifacts_path=artifacts,
                                       enable_remote_services=False,allow_external_plugins=False,
                                       do_table_structure=True,do_ocr=use_local_tesseract)
            if use_local_tesseract:
                from docling.datamodel.pipeline_options import TesseractOcrOptions
                options.ocr_options=TesseractOcrOptions(lang=['vie','eng'])
            converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
        except ImportError as e:
            raise OfflineModelError('Thiếu docling hoặc OCR backend, cần cài gói phụ thuộc offline') from e
    else:
        converter=converter_factory(artifacts)
    result=converter.convert(str(source))
    status=str(getattr(result,'status','UNKNOWN'))
    doc=getattr(result,'document',None)
    if doc is None:raise RuntimeError(f'Docling không tạo được tài liệu: {status}')
    markdown=doc.export_to_markdown()
    # Do not silently truncate: allow max 1M chars and signal limitation.
    truncated=len(markdown)>1_000_000
    return {'status':status,'markdown':markdown[:1_000_000],
            'truncated':truncated,'table_count':len(getattr(doc,'tables',[])),
            'source':'docling-local','bbox_qualified':False,
            'human_verified':False}


class DocUnwarpLocal:
    """Optional UVDoc-based curved-page preview without inverse pixel mapping.

    The result is a NEW image, not a replacement for verified source geometry.
    The user can inspect/export it and import as a new derivative document.
    """
    def __init__(self,base:Path|None=None,factory:Callable|None=None):
        prevent_remote_model_resolution()
        folder=required_model_dir('doc_unwarp',base)
        if factory is None:
            try:from paddleocr import DocPreprocessor
            except ImportError as exc:raise OfflineModelError('Cần PaddleOCR offline cho UVDoc') from exc
            factory=DocPreprocessor
        self.pipe=factory(doc_unwarping_model_dir=str(folder),
                          use_doc_unwarping=True,use_doc_orientation_classify=False)

    def unwarp(self,image:Image.Image) -> Image.Image:
        arr=np.asarray(image.convert('RGB'))
        results=list(self.pipe.predict(arr))
        if len(results)!=1:raise RuntimeError('UVDoc không tạo đúng một ảnh kết quả')
        images=getattr(results[0],'img',None)
        if callable(images):images=images()
        if not isinstance(images,dict) or 'preprocessed_img' not in images:
            raise RuntimeError('UVDoc không trả về preprocessed_img')
        value=images['preprocessed_img']
        if isinstance(value,Image.Image):return value.convert('RGB')
        output=np.asarray(value)
        if output.ndim!=3 or output.shape[2] not in (3,4):
            raise ValueError('Định dạng ảnh UVDoc không được hỗ trợ')
        return Image.fromarray(output[:,:,:3].astype('uint8')).convert('RGB')
