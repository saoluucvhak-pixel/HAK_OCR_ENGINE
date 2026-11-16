"""Advanced offline pipeline tests, no network or heavyweight model download."""
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace
import json
import pytest
import numpy as np
from PIL import Image,ImageDraw

from hak_ocr.advanced_engines import (
    OfflineModelError, PaddleLocal,paddle_result_to_blocks,merge_ocr_candidates,
    extract_docling,engine_report,DocUnwarpLocal)
from hak_ocr.models import Block,Page,Result
from hak_ocr.geometry import order_quad,warp_page,reapply_geometry
from hak_ocr.evidence_ai import extract_evidence_claims,suggest_document_matches,LocalGGUFExtractor
from hak_ocr.storage import Repository
from hak_ocr.handwriting import HandwritingLocal


def test_strict_missing_paddle_models_no_implicit_download(tmp_path):
    calls=[]
    with pytest.raises(OfflineModelError,match='Thiếu model offline'):
        PaddleLocal(tmp_path,lambda **k:calls.append(k))
    assert calls==[]


def test_paddle_mock_prediction_and_bboxes(tmp_path):
    (tmp_path/'paddle_detection').mkdir();(tmp_path/'paddle_detection'/'fake').write_text('not a weight')
    (tmp_path/'paddle_recognition').mkdir();(tmp_path/'paddle_recognition'/'fake').write_text('not a weight')
    inputs=[]
    class FakePipe:
        def predict(self,img):
            assert isinstance(img,np.ndarray)
            return [SimpleNamespace(json={'res':{'rec_texts':['BẢNG CHẤM CÔNG'],'rec_scores':[.91],
               'rec_polys':np.array([[[10,20],[110,20],[110,45],[10,45]]])}})]
    def make_pipe(**k):inputs.append(k);return FakePipe()
    engine=PaddleLocal(tmp_path,make_pipe)
    blocks=engine.recognize(Image.new('RGB',(200,100),'white'),0)
    assert blocks[0].text=='BẢNG CHẤM CÔNG'
    assert blocks[0].bbox==pytest.approx([.05,.2,.55,.45])
    assert blocks[0].confidence==pytest.approx(91.0)
    assert not inputs[0]['use_doc_unwarping']
    assert str(tmp_path) in inputs[0]['text_recognition_model_dir']


def test_hybrid_keeps_original_words_and_marks_conflicts():
    tess=[Block('bù',[0,.1,.2,.2],85),Block('công',[.21,.1,.5,.2],85)]
    p=[Block('bù cơm',[0,.1,.50,.2],99,'paddleocr-local')]
    result,alts=merge_ocr_candidates(tess,p)
    assert [b.text for b in result]==['bù','công']
    assert len(alts)==1 and alts[0]['status']=='NEEDS_REVIEW'
    assert alts[0]['paddle']=='bù cơm'


def test_docling_local_factory_does_not_download(tmp_path):
    source=tmp_path/'input.pdf';source.write_bytes(b'%PDF-1.7\n')
    with pytest.raises(OfflineModelError):
        extract_docling(source,base=tmp_path,converter_factory=lambda p:None)
    (tmp_path/'docling').mkdir();(tmp_path/'docling'/'fake').write_text('x')
    class FakeConverter:
        def convert(self,src):
            return SimpleNamespace(status='SUCCESS',document=SimpleNamespace(
                export_to_markdown=lambda:'| Họ tên | Công |\n|---|---|\n| An | 2 |',tables=[1]))
    layout=extract_docling(source,base=tmp_path,converter_factory=lambda p:FakeConverter())
    assert layout['table_count']==1 and layout['bbox_qualified'] is False
    assert layout['human_verified'] is False


def test_geometry_rectification_and_reapply_scale():
    im=Image.new('RGB',(600,500),'white')
    points=[[50,90],[525,35],[560,450],[80,465]]
    out,geom=warp_page(im,points)
    assert geom['method']=='perspective-quad'
    assert out.width>400 and out.height>350
    prev=reapply_geometry(im.resize((300,250)),geom)
    assert prev.width>200 and prev.height>170
    assert order_quad(np.array(points)).shape==(4,2)


def test_perspective_rejects_bad_coordinates():
    with pytest.raises(ValueError,match='ngoài ảnh'):
        warp_page(Image.new('RGB',(300,200)),[[-2,0],[290,0],[290,190],[0,190]])


def test_offline_handwriting_requires_files_before_import(tmp_path):
    with pytest.raises(OfflineModelError):HandwritingLocal(tmp_path)


def test_handwriting_adapter_candidate_without_verification(tmp_path,monkeypatch):
    (tmp_path/'handwriting').mkdir();(tmp_path/'handwriting'/'config.json').write_text('{}')
    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, *a, **kwargs):
            assert kwargs['local_files_only'] is True
            return cls()
        def __call__(self, **kwargs):
            return SimpleNamespace(pixel_values=np.array([1]))
        def batch_decode(self, ids, skip_special_tokens):return ['Đọc thử']
    class FakeModel:
        @classmethod
        def from_pretrained(cls,*a,**kwargs):
            assert kwargs['local_files_only'] is True
            return cls()
        def eval(self):return None
        def generate(self,*a,**kwargs):return [1]
    import sys
    class FakeTorch:
        @staticmethod
        def inference_mode():
            from contextlib import nullcontext
            return nullcontext()
    monkeypatch.setitem(sys.modules,'torch',FakeTorch)
    htr=HandwritingLocal(tmp_path,FakeProcessor,FakeModel)
    item=htr.recognize(Image.new('RGB',(200,70),'white'))
    assert item['status']=='CANDIDATE' and item['verified'] is False
    assert item['text']=='Đọc thử'


def test_attendance_message_evidence_is_not_approval():
    text=('vừa rồi em tính lương tháng 8 (ngày 15/8) cho nhân sự Nhân viên A KCS '
          'thiếu 1.5 ngày (làm tiếp ca thay cho Nhân viên B KCS). Tháng sau em bổ sung bù lương')
    claims=extract_evidence_claims(text,['Nhân viên A','Nhân viên B'])
    assert claims
    c=claims[0]
    assert c['review_state']=='PROPOSED' and not c['verified']
    assert any(q['value']==1.5 for q in c['quantities'])
    assert any(x['month']==8 for x in c['months'])
    assert 'Nhân viên A' in c['people_candidates']


def test_match_requires_verified_alias_and_no_auto_link():
    evidence='Nhân viên A thiếu 1,5 ngày công tháng 8'
    claim=extract_evidence_claims(evidence,['Nhân viên A'])
    suggestions=suggest_document_matches(claim,[{'id':'other','text':'Bảng công nhân sự Nhân viên A T8'},
                                              {'id':'evidence','text':evidence}],source_id='evidence')
    assert len(suggestions)==1
    assert suggestions[0]['relationship']=='REFERENCE'
    assert suggestions[0]['requires_manual_verification']


def test_evidence_claim_persistence_and_no_auto_payroll(tmp_path):
    file=tmp_path/'scan.png';Image.new('RGB',(150,100),'white').save(file)
    repo=Repository(tmp_path/'data')
    try:
        did,_=repo.add_file(file);doc=repo.get(did)
        sentence='tháng 8 Nhân viên A thiếu 1,5 ngày công'
        repo.save_result(Result(did,doc['sha256'],file.name,'generic',
                                pages=[Page(0,150,100,text=sentence)]))
        claims=extract_evidence_claims(sentence,['Nhân viên A'])
        ids=repo.add_evidence_claims(did,claims,run_id=repo.get(did)['run_id'])
        assert len(ids)==1
        assert repo.get(did)['status']=='NEEDS_REVIEW'
        repo.review_evidence_claim(did,ids[0],True)
        assert repo.list_evidence_claims(did)[0]['review_state']=='CONFIRMED'
        assert repo.get(did)['status']=='NEEDS_REVIEW'
        with pytest.raises(ValueError,match='truy vết'):
            repo.add_evidence_claims(did,[{'excerpt':'invented','review_state':'PROPOSED'}])
    finally:repo.close()


def test_unverified_handwriting_field_preserved(tmp_path):
    f=tmp_path/'scan.png';Image.new('RGB',(150,100),'white').save(f)
    r=Repository(tmp_path/'db')
    try:
        did,_=r.add_file(f);d=r.get(did)
        r.save_result(Result(did,d['sha256'],f.name,'generic',[Page(0,150,100,'')]))
        r.add_candidate_field(did,'chu_viet_tay','Chữ viết tay','Nguyễn',0,[.1,.1,.7,.2])
        vals=r.get_result(did)['fields']
        assert vals[0]['value']=='Nguyễn' and vals[0]['verified'] is False
        with pytest.raises(ValueError,match='đã tồn tại'):
            r.add_candidate_field(did,'chu_viet_tay','Dữ liệu mới','Ghi đè',0,[.1,.1,.7,.2])
    finally:r.close()


def test_curved_unwarp_local_preview_only(tmp_path):
    folder=tmp_path/'doc_unwarp';folder.mkdir();(folder/'fake').write_text('dummy')
    config=[]
    class FakeUV:
        def predict(self,img):
            return [SimpleNamespace(img={'preprocessed_img':Image.new('RGB',(180,130),'white')})]
    adapter=DocUnwarpLocal(tmp_path,lambda **kwargs:(config.append(kwargs),FakeUV())[1])
    out=adapter.unwarp(Image.new('RGB',(300,200),'white'))
    assert out.size==(180,130)
    assert config[0]['use_doc_unwarping'] is True
    assert config[0]['use_doc_orientation_classify'] is False
    assert 'doc_unwarp' in config[0]['doc_unwarping_model_dir']

def test_curved_unwarp_model_is_required(tmp_path):
    with pytest.raises(OfflineModelError):
        DocUnwarpLocal(tmp_path,lambda **kw:None)


def test_manual_ocr_text_keeps_original_and_can_extract_evidence(tmp_path):
    file=tmp_path/'x.png';Image.new('RGB',(150,90),'white').save(file)
    repo=Repository(tmp_path/'db')
    try:
        did,_=repo.add_file(file);doc=repo.get(did)
        repo.save_result(Result(did,doc['sha256'],file.name,'generic',
                                pages=[Page(0,150,90,'OCR nhầm chữ')]))
        repo.correct_page_text(did,0,'Nhân viên A thiếu 1,5 ngày công tháng 8')
        fixed=repo.get_result(did)['pages'][0]
        assert fixed['raw_ocr_text']=='OCR nhầm chữ'
        assert fixed['text_source']=='manual-correction'
        assert extract_evidence_claims(fixed['text'],['Nhân viên A'])
        repo.save_result(Result(did,doc['sha256'],file.name,'generic',
                                pages=[Page(0,150,90,'Bản OCR mới')]))
        assert repo.get_result(did)['pages'][0]['text']=='Bản OCR mới'
    finally:repo.close()
