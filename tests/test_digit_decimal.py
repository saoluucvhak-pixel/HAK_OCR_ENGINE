"""Regression: a visible decimal dot must never be dropped silently (1.5 -> 15)."""
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
pytest.importorskip('pytesseract')

from benchmark_digits import CONDITIONS, render_cell  # noqa: E402
from hak_ocr.deep_cells import _read_number_detailed  # noqa: E402


@pytest.mark.parametrize('value', ['1.5', '0.5'])
@pytest.mark.parametrize('size', [18, 22, 26])
def test_decimal_cells_never_lose_the_dot(value, size):
    img = render_cell(value, size, CONDITIONS['clean'], random.Random(0))
    detail = _read_number_detailed(img, 'eng')
    predicted = detail['value'] if detail else ''
    # Either the correct decimal value or an abstention; never the dot-less guess.
    assert predicted in (value, ''), f'{value} read as {predicted!r}'
