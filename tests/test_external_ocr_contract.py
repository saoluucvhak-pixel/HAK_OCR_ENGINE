import pytest
from hak_ocr.external_ocr_contract import OCRRequest, OCRCandidate, normalize_candidate, NEEDS_REVIEW

HASH = "a" * 64

@pytest.mark.parametrize("engine", ["paddleocr", "umi-ocr", "unlimited-ocr"])
def test_all_external_candidates_need_review(engine):
    req = OCRRequest("task1", HASH, "synthetic.png", "phieu_can")
    result = normalize_candidate(req, engine, "test-model", fields={"weight": {"value": "1200", "confidence": None}})
    assert result.review_status == NEEDS_REVIEW
    assert result.document_sha256 == HASH

def test_cannot_approve_raw_ocr():
    with pytest.raises(ValueError):
        OCRCandidate("task1", "paddleocr", "1", HASH, review_status="APPROVED")

def test_bad_hash_rejected():
    with pytest.raises(ValueError):
        OCRRequest("task1", "invalid", "synthetic.png", "phieu_can")

def test_unknown_engine_rejected():
    req = OCRRequest("task1", HASH, "synthetic.png", "phieu_can")
    with pytest.raises(ValueError):
        normalize_candidate(req, "unknown", "1")
