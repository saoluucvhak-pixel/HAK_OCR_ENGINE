"""engine_report phải nói rõ engine nào sẵn sàng và thiếu gì, không tải gì từ mạng."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from hak_ocr import advanced_engines as ae

ROOT = Path(__file__).resolve().parents[1]


def _fake_libs(monkeypatch, present: set[str]):
    real = importlib.util.find_spec

    def fake(name, *a, **k):
        if name in present:
            return object()
        return None if name in {'paddle','paddleocr','docling','transformers','torch','llama_cpp'} else real(name, *a, **k)

    monkeypatch.setattr(importlib.util, 'find_spec', fake)


def test_empty_model_root_reports_everything_missing(tmp_path, monkeypatch):
    _fake_libs(monkeypatch, set())
    report = ae.engine_report(tmp_path)
    assert report['network_required'] is False
    assert all(e['ready'] is False for e in report['engines'].values())
    assert 'model:paddle_detection' in report['engines']['paddle']['missing']
    assert 'library:paddleocr' in report['engines']['paddle']['missing']
    assert 'model:docling' in report['engines']['docling']['missing']


def test_readme_only_directory_is_not_a_usable_model(tmp_path, monkeypatch):
    _fake_libs(monkeypatch, set())
    (tmp_path / 'evidence_llm').mkdir()
    (tmp_path / 'evidence_llm' / 'README.md').write_text('hướng dẫn', encoding='utf-8')
    report = ae.engine_report(tmp_path)
    assert 'model:evidence_llm' in report['engines']['evidence_llm']['missing']


def test_gguf_model_and_library_make_llm_ready(tmp_path, monkeypatch):
    _fake_libs(monkeypatch, {'llama_cpp'})
    (tmp_path / 'evidence_llm').mkdir()
    (tmp_path / 'evidence_llm' / 'model.gguf').write_bytes(b'x')
    status = ae.engine_report(tmp_path)['engines']['evidence_llm']
    assert status == {'ready': True, 'missing': []}


def test_paddle_needs_both_models_and_both_libraries(tmp_path, monkeypatch):
    _fake_libs(monkeypatch, {'paddle'})
    for name in ('paddle_detection', 'paddle_recognition'):
        (tmp_path / name).mkdir()
        (tmp_path / name / 'inference.json').write_text('{}', encoding='utf-8')
    status = ae.engine_report(tmp_path)['engines']['paddle']
    assert status == {'ready': False, 'missing': ['library:paddleocr']}


def test_cli_advanced_check_prints_engine_status(tmp_path):
    out = subprocess.run([sys.executable, 'cli.py', 'advanced-check'], cwd=ROOT,
                         capture_output=True, text=True, check=True,
                         env={**__import__('os').environ, 'HAK_OCR_MODELS_DIR': str(tmp_path)}).stdout
    data = json.loads(out)
    assert set(data['engines']) == {'paddle', 'docling', 'evidence_llm'}
    assert data['network_required'] is False
