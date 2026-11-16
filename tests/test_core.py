import json
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from hak_ocr.storage import Repository
from hak_ocr.models import Page, Field, Result, Table, Block
from hak_ocr.exporting import export_result,safe_value
from hak_ocr.processing import detect_type,detect_table,normalize_bbox


def new_image(path):
    im=Image.new('RGB',(320,220),'white')
    ImageDraw.Draw(im).text((14,22),'MOCK DOCUMENT 2026',fill='black')
    im.save(path)


def setup_doc(tmp_path):
    src=tmp_path/'a.png';new_image(src)
    repo=Repository(tmp_path/'data')
    doc_id,added=repo.add_file(src)
    doc=repo.get(doc_id)
    result=Result(doc_id,doc['sha256'],'a.png','bang_cham_cong',
                  [Page(0,320,220,'Tháng 09/2026',[])],
                  [Field('tong_cong','Tổng công','3O','3O',0,[.2,.2,.4,.3])])
    repo.save_result(result)
    return repo,doc_id


def test_import_hash_and_immutable_source(tmp_path):
    repo,docid=setup_doc(tmp_path)
    try:
        source=Path(repo.get(docid)['original_path'])
        before=source.read_bytes()
        repeat,added=repo.add_file(tmp_path/'a.png')
        assert repeat==docid and not added
        assert source.read_bytes()==before
    finally:repo.close()


def test_correction_history_and_no_automatic_rule(tmp_path):
    repo,docid=setup_doc(tmp_path)
    try:
        repo.verify_field(docid,'tong_cong','30')
        item=repo.get_fields(docid)[0]
        assert item['verified']==1 and item['final_value']=='30'
        assert repo.db.execute('SELECT COUNT(*) FROM correction_events').fetchone()[0]==1
        rule=repo.list_rules()[0]
        assert rule['state']=='PROPOSED'
        assert repo.propose_suggestions(docid,'tong_cong','3O')==[]
        ok,report=repo.test_learning_rule(rule['id'])
        assert not ok
        with pytest.raises(ValueError):repo.change_rule_state(rule['id'],'ACTIVE')
        repo.verify_document(docid)
        assert repo.get(docid)['status']=='VERIFIED'
    finally:repo.close()


def test_learn_holdout_requires_3_verified_examples(tmp_path):
    repo,docid=setup_doc(tmp_path)
    repo.verify_field(docid,'tong_cong','30')
    rule=repo.list_rules()[0]
    for i in range(3):
        src=tmp_path/f'{i}.png';new_image(src)
        # Ensure different SHA-256 for each doc
        im=Image.open(src);ImageDraw.Draw(im).text((80,50),str(i),fill='black');im.save(src)
        oid,_=repo.add_file(src)
        d=repo.get(oid)
        repo.save_result(Result(oid,d['sha256'],src.name,'bang_cham_cong',[],
                                 [Field('tong_cong','Tổng công','3O','3O',0,None)]))
        repo.verify_field(oid,'tong_cong','30')
    ok,report=repo.test_learning_rule(rule['id'])
    assert ok and repo.db.execute('SELECT quality_json FROM learning_rules WHERE id=?',(rule['id'],)).fetchone()[0]
    repo.change_rule_state(rule['id'],'APPROVED')
    repo.change_rule_state(rule['id'],'ACTIVE')
    assert repo.propose_suggestions(docid,'tong_cong','3O')[0]['value']=='30'
    repo.change_rule_state(rule['id'],'ROLLED_BACK')
    assert repo.propose_suggestions(docid,'tong_cong','3O')==[]
    repo.close()


def test_verified_fields_preserved_on_ocr_rerun(tmp_path):
    repo,docid=setup_doc(tmp_path)
    repo.verify_field(docid,'tong_cong','30')
    d=repo.get(docid)
    repo.save_result(Result(docid,d['sha256'],'a.png','bang_cham_cong',[],
                            [Field('tong_cong','Tổng công','999','999',0,None)]))
    assert repo.get_fields(docid)[0]['final_value']=='30'
    assert repo.get_fields(docid)[0]['raw_value']=='999'
    repo.close()


def test_table_grid_synthetic_and_cell_corrections(tmp_path):
    from PIL import ImageDraw
    im=Image.new('RGB',(600,360),'white');d=ImageDraw.Draw(im)
    for x in (40,180,320,460,580):d.line([(x,50),(x,320)],fill='black',width=3)
    for y in (50,100,150,200,250,320):d.line([(40,y),(580,y)],fill='black',width=3)
    tables=detect_table(im,[],0)
    assert tables and len(tables[0].grid)>=3 and len(tables[0].grid[0])>=3
    repo,docid=setup_doc(tmp_path)
    tbl=tables[0];base=repo.get_result(docid)
    base['pages'][0]['tables']=[tbl.to_dict()]
    repo.db.execute('UPDATE documents SET last_result_json=? WHERE id=?',(json.dumps(base),docid));repo.db.commit()
    grid=[list(r) for r in tbl.grid]
    grid[0][0]='1'
    repo.table_edit(docid,tbl.table_id,tbl.page,grid,True)
    assert repo.get_result(docid)['pages'][0]['tables'][0]['grid'][0][0]=='1'
    assert len(repo.list_rules())>=1
    repo.verify_field(docid,'tong_cong','3O')
    repo.verify_document(docid)
    repo.close()


def test_export_office_safe(tmp_path):
    repo,docid=setup_doc(tmp_path)
    repo.verify_field(docid,'tong_cong','=1+2')
    result=repo.get_result(docid)
    jsonpath=tmp_path/'out.json';export_result(result,jsonpath)
    assert json.loads(jsonpath.read_text())['fields'][0]['value']=='=1+2'
    csvpath=tmp_path/'out.csv';export_result(result,csvpath)
    assert "'=1+2" in csvpath.read_text(encoding='utf-8-sig')
    xlsx=tmp_path/'out.xlsx';export_result(result,xlsx)
    from openpyxl import load_workbook
    wb=load_workbook(xlsx)
    assert wb.active['C8'].value=="'=1+2"
    repo.close()


def test_backup_db(tmp_path):
    repo,docid=setup_doc(tmp_path)
    backup=tmp_path/'copy.sqlite3';repo.backup(backup)
    import sqlite3
    with sqlite3.connect(backup) as con:
        assert con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==1
    repo.close()


def test_document_classification():
    assert detect_type('BẢNG CHẤM CÔNG THÁNG 9')=='bang_cham_cong'
    assert detect_type('PHIẾU CÂN xe hàng')=='phieu_can'
    assert normalize_bbox(0,0,200,100,200,100)==[0.0,0.0,1.0,1.0]


def test_attendance_null_and_decimal_validation():
    from hak_ocr.validation import parse_attendance_value,validate_attendance_grid
    assert parse_attendance_value('') is None
    assert parse_attendance_value('-') is None
    assert parse_attendance_value('0')==0
    assert parse_attendance_value('0,5')==0.5
    assert parse_attendance_value('2')==2
    assert parse_attendance_value('O.5') is None
    grid=[['Nhân viên','1','2','3','4','5','TC'],
          ['A','1','1','1','1','1','5'],
          ['B','1','1','', '1','1','5']]
    issues=validate_attendance_grid(grid)
    assert len(issues)==1 and issues[0]['row']==3


def test_complete_backup_restore(tmp_path):
    from hak_ocr.backup import backup_complete,restore_complete
    repo,docid=setup_doc(tmp_path)
    bundle=tmp_path/'safe.zip'
    backup_complete(repo,bundle)
    repo.close()
    newhome=tmp_path/'restored'
    restore_complete(bundle,newhome)
    restored=Repository(newhome)
    assert Path(restored.get(docid)['original_path']).is_file()
    assert restored.get_result(docid)['fields'][0]['value']=='3O'
    restored.close()
    with pytest.raises(ValueError):restore_complete(bundle,newhome)


def test_template_specs(tmp_path):
    from hak_ocr.templates import DEFAULT_ATTENDANCE_TEMPLATE,extract_template_fields
    page=Page(0,800,400,'Bảng chấm công Tháng 09/2026')
    fields=extract_template_fields([page],[DEFAULT_ATTENDANCE_TEMPLATE],'bang_cham_cong')
    assert fields and fields[0].value=='09/2026'
    repo=Repository(tmp_path/'data');repo.save_template(DEFAULT_ATTENDANCE_TEMPLATE)
    assert repo.list_templates()[0]['id']=='attendance-basic-v1'
    repo.close()


def test_deep_cell_does_not_invent_zero_for_blank():
    from hak_ocr.deep_cells import _read_number
    from PIL import Image
    assert _read_number(Image.new('RGB',(60,32),'white'))==''


def test_cannot_verify_import_only(tmp_path):
    src=tmp_path/'document.png';new_image(src)
    repo=Repository(tmp_path/'data')
    docid,_=repo.add_file(src)
    with pytest.raises(ValueError):repo.verify_document(docid)
    repo.close()


def test_pdf_native_text_routing(tmp_path):
    import fitz
    from hak_ocr.processing import process_file
    source=tmp_path/'native.pdf'
    doc=fitz.open();p=doc.new_page()
    p.insert_text((30,60),'Invoice Date 01-09-2026 Contract number ABC-1000 employee shift hours meal allowance salary',fontsize=11)
    p.insert_text((30,90),'More words to exceed threshold of native PDF text, avoiding OCR duplication during extraction',fontsize=11)
    doc.save(source);doc.close()
    repo=Repository(tmp_path/'data')
    docid,_=repo.add_file(source);d=repo.get(docid)
    res=process_file(d['original_path'],docid,d['sha256'],detect_rotation=False)
    assert res.pages[0].source=='pdf-text'
    assert any(b.engine=='pdf-text' for b in res.pages[0].blocks)
    repo.close()
