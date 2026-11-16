from pathlib import Path
from hak_ocr.selftest import check_packaged_app
from hak_ocr.config import resource_root


def test_source_distribution_has_docs():
    root=resource_root()
    assert (root / 'README_WINDOWS_EXE.md').is_file()
    assert (root / 'scripts' / 'build_windows_release.ps1').is_file()


def test_source_build_is_not_misrepresented_as_exe():
    import sys
    assert not bool(getattr(sys,'frozen',False))
    assert Path(__file__).suffix=='.py'


def test_selftest_reports_explicit_runtime_state():
    report=check_packaged_app(require_bundled=True)
    assert 'ok' in report and 'checks' in report
    # A Windows build runner may already have bundled OCR runtime during tests.
    assert report['ok'] == all(report['checks'].get(k, False) for k in report['required_checks'])
    assert isinstance(report['checks']['bundled_tesseract_file'], bool)