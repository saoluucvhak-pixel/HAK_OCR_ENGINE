"""Bộ đọc tùy chọn Unlimited-OCR (Baidu, MIT) — chạy CỤC BỘ, cần GPU NVIDIA.

Theo đúng nguyên tắc của advanced_engines.py:
- Bắt buộc có thư mục model cục bộ `vendor/models/unlimited_ocr` (hoặc trong HAK_OCR_MODELS_DIR).
  Không tự tải, không chuyển sang dịch vụ mạng.
- Import torch/transformers chỉ khi gọi tới.
- Kết quả luôn là GỢI Ý chưa duyệt, như mọi engine khác.

⚠ Model này dùng `trust_remote_code=True`, tức là chạy mã Python đi kèm thư mục model.
  Chỉ dùng thư mục model tải từ nguồn chính chủ (huggingface.co/baidu/Unlimited-OCR) và đã kiểm tra.

Cài thêm: torch bản CUDA + `pip install transformers==4.57.1 einops`.
Tiếng Việt: tài liệu gốc không công bố danh sách ngôn ngữ — phải thử trên chứng từ thật trước khi dùng.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from PIL import Image

from .advanced_engines import OfflineModelError, prevent_remote_model_resolution, required_model_dir

MODEL_NAME = 'unlimited_ocr'


def unlimited_status(base: Path | None = None) -> dict:
    libs = {x: importlib.util.find_spec(x) is not None for x in ('torch', 'transformers', 'einops')}
    try:
        model = str(required_model_dir(MODEL_NAME, base))
    except OfflineModelError as exc:
        model = None
        reason = str(exc)
    else:
        reason = ''
    cuda = False
    if libs['torch']:
        import torch
        cuda = bool(torch.cuda.is_available())
    return {'model_dir': model, 'libraries': libs, 'cuda': cuda,
            'ready': bool(model) and all(libs.values()) and cuda, 'reason': reason}


class UnlimitedOCRLocal:
    """Đọc một ảnh trang tài liệu → văn bản có cấu trúc. Khởi tạo nặng (~6 GB), nên tạo một lần, dùng nhiều lần."""

    def __init__(self, models_dir: Path | None = None, allow_cpu: bool = False, max_length: int = 32768):
        path = required_model_dir(MODEL_NAME, models_dir)  # kiểm tra model TRƯỚC khi import thư viện nặng
        prevent_remote_model_resolution()
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise OfflineModelError('Chưa cài torch/transformers/einops cho Unlimited-OCR.') from exc
        if not torch.cuda.is_available() and not allow_cpu:
            raise OfflineModelError('Unlimited-OCR cần GPU NVIDIA (khuyến nghị 8–12 GB VRAM). Dùng Tesseract, hoặc allow_cpu=True (rất chậm).')
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        dtype = torch.bfloat16 if device == 'cuda' else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), trust_remote_code=True, local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), trust_remote_code=True, local_files_only=True,
                                               torch_dtype=dtype).eval().to(device)
        self.max_length = max_length

    def read(self, image: Image.Image) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'page.png'
            image.convert('RGB').save(p)
            out = self.model.infer(self.tokenizer, prompt='<image>document parsing.', image_file=str(p),
                                   output_path=tmp, base_size=1024, image_size=640, crop_mode=True,
                                   max_length=self.max_length)
        if isinstance(out, (list, tuple)):
            out = '\n'.join(str(x) for x in out)
        return (str(out) if out is not None else '').strip()
