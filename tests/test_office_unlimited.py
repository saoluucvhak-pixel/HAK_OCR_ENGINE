"""Bộ đọc văn phòng (MarkItDown) và adapter Unlimited-OCR tùy chọn."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hak_ocr.advanced_engines import OfflineModelError, engine_report
from hak_ocr.office import OfficeConversionError, convert_office, is_office_file
from hak_ocr.unlimited_engine import UnlimitedOCRLocal, unlimited_status

ROOT = Path(__file__).resolve().parents[1]
markitdown = pytest.importorskip("markitdown", reason="chưa cài requirements-office.txt")


def test_csv_ra_bang_markdown(tmp_path):
    p = tmp_path / "phieu_can.csv"
    p.write_text("Phiếu cân,KL hàng (Tấn)\nPC0001,6.9\n", encoding="utf-8")
    res = convert_office(p)
    assert res.kind == "csv" and len(res.sha256) == 64
    assert "PC0001" in res.markdown and "6.9" in res.markdown and "|" in res.markdown


def test_xlsx_giu_chu_tieng_viet(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Mã NV", "Họ và tên", "Tổng công"]); ws.append(["NV01", "Nguyễn Văn Ửng", 26])
    p = tmp_path / "cong.xlsx"; wb.save(p)
    md = convert_office(p).markdown
    assert "Nguyễn Văn Ửng" in md and "Tổng công" in md


def test_tu_choi_url_pdf_anh_va_dinh_dang_la(tmp_path):
    with pytest.raises(OfficeConversionError, match="cục bộ"):
        convert_office("https://example.com/a.docx")
    for name, msg in (("a.pdf", "OCR"), ("a.png", "OCR"), ("a.exe", "chưa hỗ trợ")):
        f = tmp_path / name; f.write_bytes(b"x")
        with pytest.raises(OfficeConversionError, match=msg):
            convert_office(f)
    with pytest.raises(OfficeConversionError, match="Không tìm thấy"):
        convert_office(tmp_path / "khong-co.docx")
    assert is_office_file("x.DOCX") and not is_office_file("x.pdf")


def test_file_hong_bao_loi_ro(tmp_path):
    p = tmp_path / "hong.xlsx"; p.write_bytes(b"khong phai xlsx")
    with pytest.raises(OfficeConversionError, match="Không đọc được"):
        convert_office(p)


def test_cli_office_json(tmp_path):
    p = tmp_path / "a.csv"; p.write_text("a,b\n1,2\n", encoding="utf-8")
    out = subprocess.run([sys.executable, "cli.py", "office", str(p), "--json"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    assert data["kind"] == "csv" and "1" in data["markdown"]


def test_unlimited_thieu_model_bao_loi_truoc_khi_nap_thu_vien(tmp_path):
    with pytest.raises(OfflineModelError, match="Thiếu model offline"):
        UnlimitedOCRLocal(models_dir=tmp_path)
    st = unlimited_status(tmp_path)
    assert st["ready"] is False and st["model_dir"] is None and "Thiếu model" in st["reason"]


def test_unlimited_co_trong_bao_cao_engine(tmp_path):
    assert "unlimited_ocr" in engine_report(tmp_path)["models"]
    assert engine_report(tmp_path)["network_required"] is False


def test_cli_unlimited_check(tmp_path):
    out = subprocess.run([sys.executable, "cli.py", "unlimited-ocr", "--check", "--models-dir", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["ready"] is False
