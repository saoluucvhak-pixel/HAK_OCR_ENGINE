"""Đọc tài liệu văn phòng (Word, Excel, PowerPoint, HTML, CSV) ra Markdown bằng MarkItDown (Microsoft, MIT).

Phạm vi: chỉ FILE CỤC BỘ có sẵn chữ. PDF và ảnh đi qua quy trình OCR chính (processing.py),
vì MarkItDown không OCR được bản scan. Không mở URL, không gọi dịch vụ mạng, không bật plugin.

Cài thêm (tùy chọn):  pip install -r requirements-office.txt
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path

OFFICE_EXTENSIONS = {'.docx', '.xlsx', '.xls', '.pptx', '.html', '.htm', '.csv'}
ROUTE_TO_OCR = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp'}
MAX_BYTES = 50 * 1024 * 1024


class OfficeConversionError(RuntimeError):
    pass


@dataclass
class OfficeResult:
    source: str
    kind: str
    sha256: str
    markdown: str

    def to_dict(self) -> dict:
        return asdict(self)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _check_signature(p: Path, ext: str) -> None:
    """MarkItDown có thể lặng lẽ đọc file hỏng như văn bản thường — kiểm tra chữ ký file trước."""
    import zipfile
    if ext in {'.docx', '.xlsx', '.pptx'} and not zipfile.is_zipfile(p):
        raise OfficeConversionError(f'Không đọc được {p.name}: file hỏng hoặc không đúng định dạng {ext}.')
    if ext == '.xls':
        with p.open('rb') as f:
            if f.read(8) != bytes.fromhex('D0CF11E0A1B11AE1'):
                raise OfficeConversionError(f'Không đọc được {p.name}: file hỏng hoặc không đúng định dạng .xls.')


def is_office_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in OFFICE_EXTENSIONS


def convert_office(path: str | Path) -> OfficeResult:
    """Chuyển một file văn phòng cục bộ thành Markdown. Bảng Excel/Word giữ dạng bảng Markdown."""
    raw = str(path)
    if '://' in raw:
        raise OfficeConversionError('Chỉ nhận file cục bộ, không nhận đường dẫn mạng.')
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise OfficeConversionError(f'Không tìm thấy file: {p}')
    ext = p.suffix.lower()
    if ext in ROUTE_TO_OCR:
        raise OfficeConversionError(f'{ext} cần đi qua OCR (cli.py import-and-ocr), không qua bộ đọc văn phòng.')
    if ext not in OFFICE_EXTENSIONS:
        raise OfficeConversionError(f'Định dạng {ext or "(không có đuôi)"} chưa hỗ trợ. Hỗ trợ: {", ".join(sorted(OFFICE_EXTENSIONS))}')
    if p.stat().st_size > MAX_BYTES:
        raise OfficeConversionError('File lớn hơn 50 MB.')
    _check_signature(p, ext)
    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # gói tùy chọn
        raise OfficeConversionError('Chưa cài MarkItDown. Chạy: pip install -r requirements-office.txt') from exc
    try:
        text = MarkItDown(enable_plugins=False).convert_local(str(p)).text_content
    except Exception as exc:  # file hỏng, có mật khẩu…
        raise OfficeConversionError(f'Không đọc được {p.name}: {exc}') from exc
    return OfficeResult(source=str(p), kind=ext.lstrip('.'), sha256=_sha256(p), markdown=(text or '').strip())
