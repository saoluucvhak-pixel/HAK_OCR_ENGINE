from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import uuid
from .config import ensure_dirs
from .models import Result, Field


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dump(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def table_layout_signature(table: dict) -> str:
    """Fingerprint grid geometry, not OCR text, to prevent stale reviews.

    Rounded normalized boxes permit insignificant coordinate noise while
    detecting added/removed rows, columns and materially changed locations.
    """
    layout={
        'shape':[len(row) for row in table.get('grid',[])],
        'bbox':[round(float(x),3) for x in table.get('bbox',[])],
        'boxes':[[[round(float(x),3) for x in cell] for cell in row]
                 for row in table.get('cell_boxes',[])],
    }
    return sha256(json_dump(layout).encode('utf-8')).hexdigest()


class Repository:
    """Single-user local SQLite store. New OCR runs never overwrite human reviews."""
    def __init__(self, home: Path | None = None):
        self.home = ensure_dirs(home)
        self.path = self.home / "hak_ocr.sqlite3"
        self.db = sqlite3.connect(str(self.path), timeout=20, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA busy_timeout = 10000")
        self._init_schema()

    def _init_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
           id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
           original_name TEXT NOT NULL, original_path TEXT NOT NULL,
           document_type TEXT NOT NULL DEFAULT 'generic', status TEXT NOT NULL DEFAULT 'IMPORTED',
           created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
           last_result_json TEXT, run_id TEXT
        );
        CREATE TABLE IF NOT EXISTS fields (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           field_key TEXT NOT NULL, label TEXT NOT NULL,
           raw_value TEXT, final_value TEXT NOT NULL,
           page INTEGER, bbox_json TEXT, confidence REAL,
           verified INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0,
           UNIQUE(document_id,field_key)
        );
        CREATE TABLE IF NOT EXISTS correction_events (
           id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           field_key TEXT NOT NULL, old_value TEXT NOT NULL, new_value TEXT NOT NULL,
           document_type TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL,
           source_bbox_json TEXT, verified INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_corrections_scope ON correction_events(document_type,field_key);
        CREATE TABLE IF NOT EXISTS learning_rules (
           id TEXT PRIMARY KEY, document_type TEXT NOT NULL, field_key TEXT NOT NULL,
           from_value TEXT NOT NULL, to_value TEXT NOT NULL,
           state TEXT NOT NULL DEFAULT 'PROPOSED',
           example_count INTEGER NOT NULL DEFAULT 1,
           correction_id TEXT NOT NULL, created_at TEXT NOT NULL,
           activated_at TEXT, quality_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_rule_scope ON learning_rules(document_type,field_key,state);
        CREATE TABLE IF NOT EXISTS jobs (
           id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
           state TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           document_id TEXT, event TEXT NOT NULL, payload_json TEXT NOT NULL,
           created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS templates (
           id TEXT PRIMARY KEY, name TEXT NOT NULL, document_type TEXT NOT NULL,
           spec_json TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_links (
           id TEXT PRIMARY KEY,
           document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           related_document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           relationship TEXT NOT NULL CHECK(relationship IN ('SUPPORTS','CONTRADICTS','REFERENCE')),
           note TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL,
           created_at TEXT NOT NULL,
           CHECK(document_id<>related_document_id),
           UNIQUE(document_id,related_document_id,relationship)
        );
        CREATE TABLE IF NOT EXISTS page_text_corrections (
           document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           page INTEGER NOT NULL, source_run_id TEXT NOT NULL,
           corrected_text TEXT NOT NULL, reviewer TEXT NOT NULL,
           updated_at TEXT NOT NULL, PRIMARY KEY(document_id,page,source_run_id)
        );
        CREATE TABLE IF NOT EXISTS evidence_claims (
           id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           source_run_id TEXT NOT NULL, claim_json TEXT NOT NULL,
           review_state TEXT NOT NULL DEFAULT 'PROPOSED' CHECK(review_state IN ('PROPOSED','REJECTED','CONFIRMED')),
           reviewer TEXT, reviewed_at TEXT,created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_doc ON evidence_claims(document_id,created_at);
        CREATE TABLE IF NOT EXISTS table_edits (
           document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
           table_id TEXT NOT NULL, page INTEGER NOT NULL,
           grid_json TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
           updated_at TEXT NOT NULL, geometry_valid INTEGER NOT NULL DEFAULT 1,
           source_signature TEXT,
           PRIMARY KEY(document_id,table_id)
        );
        ''')
        columns={row[1] for row in self.db.execute('PRAGMA table_info(learning_rules)')}
        if 'quality_json' not in columns:
            self.db.execute('ALTER TABLE learning_rules ADD COLUMN quality_json TEXT')
        table_columns={row[1] for row in self.db.execute('PRAGMA table_info(table_edits)')}
        if 'geometry_valid' not in table_columns:
            self.db.execute('ALTER TABLE table_edits ADD COLUMN geometry_valid INTEGER NOT NULL DEFAULT 1')
        if 'source_signature' not in table_columns:
            self.db.execute('ALTER TABLE table_edits ADD COLUMN source_signature TEXT')
        self.db.commit()

    @staticmethod
    def checksum(src: Path) -> str:
        h = sha256()
        with src.open("rb") as fd:
            for chunk in iter(lambda: fd.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def add_file(self, filename: str | Path) -> tuple[str, bool]:
        source = Path(filename).resolve(strict=True)
        if source.suffix.lower() not in {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.pdf'}:
            raise ValueError("Định dạng ảnh/PDF chưa được hỗ trợ")
        if source.stat().st_size > 250 * 1024 * 1024:
            raise ValueError("Tệp vượt quá giới hạn 250 MB")
        signature = source.open('rb').read(16)
        if source.suffix.lower() == '.pdf' and not signature.startswith(b'%PDF-'):
            raise ValueError("Tệp PDF không có chữ ký định dạng hợp lệ")
        if source.suffix.lower() != '.pdf':
            from PIL import Image
            with Image.open(source) as im:
                im.verify()
        digest = self.checksum(source)
        known = self.db.execute("SELECT id FROM documents WHERE sha256=?", (digest,)).fetchone()
        if known:
            return known['id'], False
        doc_id = uuid.uuid4().hex
        target = self.home / "originals" / (doc_id + source.suffix.lower())
        shutil.copy2(source, target)
        current = now()
        with self.db:
            self.db.execute("INSERT INTO documents(id,sha256,original_name,original_path,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (doc_id,digest,source.name,str(target),current,current))
            self.audit(doc_id, 'IMPORTED', {'filename': source.name, 'sha256': digest})
        return doc_id, True

    def audit(self, doc_id: str | None, event: str, details: dict):
        self.db.execute("INSERT INTO audit(document_id,event,payload_json,created_at) VALUES(?,?,?,?)",
                        (doc_id,event,json_dump(details),now()))

    def get(self, doc_id: str):
        r = self.db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if r is None:
            raise KeyError(doc_id)
        return dict(r)

    def list_docs(self):
        return [dict(x) for x in self.db.execute("SELECT * FROM documents ORDER BY created_at DESC")]

    def set_status(self, doc_id: str, status: str):
        with self.db:
            self.db.execute("UPDATE documents SET status=?,updated_at=? WHERE id=?", (status,now(),doc_id))
            self.audit(doc_id,'STATUS',{'state':status})

    def save_result(self, result: Result):
        if not result.run_id:result.run_id=uuid.uuid4().hex
        with self.db:
            self.db.execute("UPDATE documents SET document_type=?, status=?,last_result_json=?,run_id=?,updated_at=? WHERE id=?",
                (result.document_type,result.status,json_dump(result.to_dict()),result.run_id,now(),result.document_id))
            for f in result.fields:
                self.db.execute('''INSERT INTO fields(document_id,field_key,label,raw_value,final_value,page,bbox_json,confidence,verified)
                                    VALUES (?,?,?,?,?,?,?,?,0)
                                    ON CONFLICT(document_id,field_key) DO UPDATE SET
                                    label=excluded.label,raw_value=excluded.raw_value,
                                    final_value=CASE WHEN fields.verified=1 THEN fields.final_value ELSE excluded.final_value END,
                                    page=excluded.page,bbox_json=excluded.bbox_json,
                                    confidence=excluded.confidence''',
                    (result.document_id,f.key,f.label,f.raw,f.value,f.page,json_dump(f.bbox),f.confidence))
            self.audit(result.document_id,'OCR_FINISHED',{'run_id':result.run_id, 'pages': len(result.pages)})

    def get_result(self, doc_id: str) -> dict | None:
        d = self.get(doc_id)
        if not d['last_result_json']:
            return None
        result = json.loads(d['last_result_json'])
        fields = self.get_fields(doc_id)
        lookup = {f['field_key']: f for f in fields}
        for f in result['fields']:
            if f['key'] in lookup:
                dbf = lookup[f['key']]
                f['value'] = dbf['final_value']
                f['verified'] = bool(dbf['verified'])
        result['status'] = d['status']
        for page in result.get('pages',[]):
            correction=self.db.execute('SELECT corrected_text,reviewer,updated_at FROM page_text_corrections WHERE document_id=? AND page=? AND source_run_id=?',
                                       (doc_id,page['number'],d['run_id'])).fetchone()
            if correction:
                page['raw_ocr_text']=page['text']
                page['text']=correction['corrected_text']
                page['text_source']='manual-correction'
                page['corrected_at']=correction['updated_at']
            for table in page.get('tables',[]):
                row = self.db.execute('SELECT grid_json,verified,geometry_valid,source_signature FROM table_edits WHERE document_id=? AND table_id=?',(doc_id,table['table_id'])).fetchone()
                if row:
                    if row['source_signature']!=table_layout_signature(table):
                        table['verified']=False
                        table['geometry_warning']='Bảng OCR đã đổi cấu trúc/vị trí: bản duyệt cũ lưu lại nhưng không áp vào lưới mới.'
                    else:
                        table['grid']=json.loads(row['grid_json'])
                        table['verified']=bool(row['verified']) and bool(row['geometry_valid'])
                        if not row['geometry_valid']:
                            table['cell_boxes']=[]
                            table['geometry_warning']='Thêm/bớt hàng cột: chưa ánh xạ được ô mới về ảnh gốc. Không thể duyệt toàn chứng từ.'
        if result.get('document_type')=='bang_cham_cong':
            from .attendance import analyse_attendance
            result['attendance_analysis']=analyse_attendance(result)
        result['evidence_links']=self.list_evidence(doc_id)
        return result

    def add_evidence_claims(self,doc_id: str,claims: list[dict],*,run_id: str | None=None) -> list[str]:
        """Save candidate claims with exact OCR-source spans; no auto approval."""
        d=self.get(doc_id)
        current=json.loads(d['last_result_json']) if d['last_result_json'] else None
        if not current:raise ValueError('Cần OCR chứng từ trước khi đọc bằng chứng')
        source_text='\n'.join(p.get('text','') for p in current.get('pages',[]))
        if run_id and run_id!=d['run_id']:
            raise ValueError('Kết quả OCR đã đổi; không thể ghi nhận claims cũ')
        ids=[]
        with self.db:
            for claim in claims[:100]:
                excerpt=str(claim.get('excerpt',''))
                if not excerpt or excerpt not in source_text:
                    raise ValueError('Claim không truy vết được đúng trích đoạn văn bản OCR')
                if claim.get('verified') or claim.get('review_state')!='PROPOSED':
                    raise ValueError('Ứng viên AI phải bắt đầu ở trạng thái PROPOSED')
                cid=uuid.uuid4().hex
                self.db.execute('INSERT INTO evidence_claims (id,document_id,source_run_id,claim_json,created_at) VALUES(?,?,?,?,?)',
                                (cid,doc_id,d['run_id'],json_dump(claim),now()))
                ids.append(cid)
            self.audit(doc_id,'CLAIMS_PROPOSED',{'count':len(ids),'run_id':d['run_id']})
        return ids

    def list_evidence_claims(self,doc_id:str) -> list[dict]:
        items=[]
        for r in self.db.execute('SELECT * FROM evidence_claims WHERE document_id=? ORDER BY created_at DESC',(doc_id,)):
            item=dict(r)
            item['claim']=json.loads(item.pop('claim_json'))
            items.append(item)
        return items

    def review_evidence_claim(self,doc_id:str,claim_id:str,approve:bool,reviewer:str='local_user'):
        state='CONFIRMED' if approve else 'REJECTED'
        with self.db:
            row=self.db.execute('SELECT review_state FROM evidence_claims WHERE id=? AND document_id=?',
                                (claim_id,doc_id)).fetchone()
            if row is None:raise KeyError(claim_id)
            self.db.execute('UPDATE evidence_claims SET review_state=?,reviewer=?,reviewed_at=? WHERE id=?',
                            (state,reviewer,now(),claim_id))
            self.audit(doc_id,'EVIDENCE_CLAIM_REVIEW',{'claim_id':claim_id,'state':state})
        # CONFIRMED means *text content reviewed*, NOT payroll approval.

    def correct_page_text(self,doc_id:str,page:int,text:str,reviewer:str='local_user') -> None:
        # Keep manually repaired OCR text separately, preserve OCR original.
        doc=self.get(doc_id)
        if not doc['last_result_json']:raise ValueError('Chưa OCR chứng từ')
        result=json.loads(doc['last_result_json'])
        if not any(p['number']==page for p in result['pages']):raise ValueError('Sai chỉ số trang')
        if len(text)>2_000_000:raise ValueError('Văn bản quá dài')
        with self.db:
            self.db.execute('INSERT INTO page_text_corrections (document_id,page,source_run_id,corrected_text,reviewer,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(document_id,page,source_run_id) DO UPDATE SET corrected_text=excluded.corrected_text,reviewer=excluded.reviewer,updated_at=excluded.updated_at',
                (doc_id,page,doc['run_id'],str(text),reviewer,now()))
            self.db.execute("UPDATE documents SET status='NEEDS_REVIEW',updated_at=? WHERE id=?",(now(),doc_id))
            self.audit(doc_id,'PAGE_TEXT_CORRECTED',{'page':page,'source_run_id':doc['run_id'],
                                                     'old_text_preserved':True})

    def add_candidate_field(self,doc_id:str,key:str,label:str,value:str,page:int,
                            bbox:list[float],source:str='handwriting-trocr') -> str:
        """Add unverified handwriting OCR field, leave existing verified fields untouched."""
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',key):raise ValueError('Mã trường chỉ gồm a-z, 0-9, _ hoặc -')
        if len(str(value))>4000 or len(label)>150:raise ValueError('Trường quá dài')
        if len(bbox)!=4 or not all(0<=float(x)<=1 for x in bbox):raise ValueError('Vùng nguồn sai')
        d=self.get(doc_id)
        if not d['last_result_json']:raise ValueError('Chưa OCR tài liệu')
        result=json.loads(d['last_result_json'])
        if not any(p['number']==page for p in result['pages']):raise ValueError('Không tồn tại trang')
        if any(f['key']==key for f in result.get('fields',[])):
            raise ValueError('Mã trường đã tồn tại; không được ghi đè trường đã duyệt')
        f={'key':key,'label':label,'raw':str(value),'value':str(value),'page':page,
           'bbox':bbox,'confidence':None,'verified':False,'source':source,'template_id':'manual-htr'}
        result['fields'].append(f)
        with self.db:
            self.db.execute('INSERT INTO fields(document_id,field_key,label,raw_value,final_value,page,bbox_json,confidence,verified) VALUES(?,?,?,?,?,?,?,?,0)',
                            (doc_id,key,label,str(value),str(value),page,json_dump(bbox),None))
            self.db.execute("UPDATE documents SET last_result_json=?,status='NEEDS_REVIEW',updated_at=? WHERE id=?",
                            (json_dump(result),now(),doc_id))
            self.audit(doc_id,'HANDWRITING_CANDIDATE',{'key':key,'bbox':bbox,'source':source})
        return key

    def list_evidence(self,doc_id: str) -> list[dict]:
        return [dict(x) for x in self.db.execute('''
            SELECT e.*,d.original_name AS related_filename,d.status AS related_status
            FROM evidence_links e JOIN documents d ON d.id=e.related_document_id
            WHERE e.document_id=? ORDER BY e.created_at''',(doc_id,))]

    def add_evidence(self,doc_id: str,related_id: str,relationship: str,
                     note: str='',reviewer: str='local_user') -> str:
        if relationship not in ('SUPPORTS','CONTRADICTS','REFERENCE'):
            raise ValueError('Quan hệ chứng từ không hợp lệ')
        if doc_id==related_id:raise ValueError('Không được tự liên kết một chứng từ')
        self.get(doc_id);self.get(related_id)
        if len(note)>2000:raise ValueError('Ghi chú quá dài')
        link_id=uuid.uuid4().hex
        with self.db:
            self.db.execute('''INSERT INTO evidence_links
                (id,document_id,related_document_id,relationship,note,reviewer,created_at)
                VALUES(?,?,?,?,?,?,?)''', (link_id,doc_id,related_id,relationship,note,reviewer,now()))
            self.audit(doc_id,'EVIDENCE_LINK_ADDED',{'related_id':related_id,'relationship':relationship})
        return link_id

    def remove_evidence(self,doc_id: str,link_id: str):
        with self.db:
            cursor=self.db.execute('DELETE FROM evidence_links WHERE id=? AND document_id=?',(link_id,doc_id))
            if not cursor.rowcount:raise KeyError(link_id)
            self.audit(doc_id,'EVIDENCE_LINK_REMOVED',{'id':link_id})

    def get_fields(self, doc_id: str) -> list[dict]:
        return [dict(x) for x in self.db.execute("SELECT * FROM fields WHERE document_id=? ORDER BY id",(doc_id,))]

    def verify_field(self, doc_id: str, key: str, value: str, reviewer: str = 'local_user'):
        with self.db:
            field = self.db.execute("SELECT * FROM fields WHERE document_id=? AND field_key=?", (doc_id,key)).fetchone()
            if not field: raise KeyError(key)
            value = str(value)
            old = field['final_value']
            self.db.execute("UPDATE fields SET final_value=?,verified=1,revision=revision+1 WHERE id=?", (value,field['id']))
            if old != value:
                correction_id = uuid.uuid4().hex
                doc_type = self.get(doc_id)['document_type']
                self.db.execute('''INSERT INTO correction_events
                    (id,document_id,field_key,old_value,new_value,document_type,reviewer,created_at,source_bbox_json)
                    VALUES(?,?,?,?,?,?,?,?,?)''',
                    (correction_id,doc_id,key,old,value,doc_type,reviewer,now(),field['bbox_json']))
                # Every correction is recorded as a scoped, NON-ACTIVE rule proposal.
                self.db.execute('''INSERT INTO learning_rules
                     (id,document_type,field_key,from_value,to_value,correction_id,created_at)
                     VALUES(?,?,?,?,?,?,?)''',
                     (uuid.uuid4().hex,doc_type,key,old,value,correction_id,now()))
                self.audit(doc_id,'CORRECTION',{'key':key,'old':old,'new':value,'reviewer':reviewer})
            else:
                self.audit(doc_id,'VERIFICATION',{'key':key, 'reviewer': reviewer})
            self.db.execute("UPDATE documents SET status='NEEDS_REVIEW', updated_at=? WHERE id=?",(now(),doc_id))

    def verify_document(self,doc_id: str):
        if self.get_result(doc_id) is None:
            raise ValueError('Chứng từ chưa được OCR, không thể xác nhận')
        with self.db:
            count = self.db.execute("SELECT count(*) as n FROM fields WHERE document_id=? AND verified=0", (doc_id,)).fetchone()['n']
            if count:
                raise ValueError(f"Còn {count} trường chưa xác nhận")
            result=self.get_result(doc_id)
            expected={t['table_id'] for p in (result or {}).get('pages',[]) for t in p.get('tables',[])}
            if expected-self.verified_table_ids(doc_id):
                raise ValueError("Còn bảng chưa xác nhận: "+', '.join(sorted(expected-self.verified_table_ids(doc_id))))
            if result.get('document_type')=='bang_cham_cong':
                from .attendance import analyse_attendance
                for analysis in analyse_attendance(result):
                    if analysis['kind']=='vertical_daily' and any(x.get('inferred_day') for x in analysis['records']):
                        raise ValueError('Còn nhãn ngày OCR chưa khớp thứ tự; phải sửa và kiểm tra từng nhãn ngày trước khi duyệt.')
            self.db.execute("UPDATE documents SET status='VERIFIED',updated_at=? WHERE id=?", (now(),doc_id))
            self.audit(doc_id,'DOCUMENT_VERIFIED',{})

    def table_edit(self, doc_id: str, table_id: str, page: int, grid: list[list[str]], verified: bool):
        # Compare against the last saved grid rather than reusing the original
        # OCR version.  Re-saving the same reviewed values must not create
        # duplicate learning events.
        if not grid or sum(len(row) for row in grid)>8000:
            raise ValueError('Bảng trống hoặc quá lớn (tối đa 8000 ô)')
        d=self.get(doc_id)
        raw=next((t for p in (json.loads(d['last_result_json']) if d['last_result_json'] else {}).get('pages',[])
                  for t in p.get('tables',[]) if t['table_id']==table_id),None)
        if raw is None:raise KeyError('Không tìm thấy bảng trong tài liệu')
        signature=table_layout_signature(raw)
        previous=self.db.execute('SELECT grid_json,geometry_valid,source_signature FROM table_edits WHERE document_id=? AND table_id=?',
                                 (doc_id,table_id)).fetchone()
        prior_is_current=bool(previous and previous['source_signature']==signature)
        before=json.loads(previous['grid_json']) if prior_is_current else raw['grid']
        structure_changed=len(before)!=len(grid) or any(len(x)!=len(y) for x,y in zip(before,grid))
        doc_type=d['document_type']
        with self.db:
            if before is not None and verified and not structure_changed:
                for ri,row in enumerate(grid):
                    for ci,newval in enumerate(row):
                        # Newly inserted cells are structural changes; they
                        # have no trustworthy OCR-origin bounding box.
                        if ri>=len(before) or ci>=len(before[ri]):continue
                        old=before[ri][ci]
                        if old!=newval:
                            correction_id=uuid.uuid4().hex
                            scope=f'table:{table_id}:row:{ri}:col:{ci}'
                            boxes=raw.get('cell_boxes') or []
                            bbox=boxes[ri][ci] if ri<len(boxes) and ci<len(boxes[ri]) else None
                            self.db.execute('INSERT INTO correction_events (id,document_id,field_key,old_value,new_value,document_type,reviewer,created_at,source_bbox_json) VALUES (?,?,?,?,?,?,?,?,?)',
                                            (correction_id,doc_id,scope,old,newval,doc_type,'local_user',now(),json_dump(bbox)))
                            self.db.execute('INSERT INTO learning_rules (id,document_type,field_key,from_value,to_value,correction_id,created_at) VALUES (?,?,?,?,?,?,?)',
                                            (uuid.uuid4().hex,doc_type,scope,old,newval,correction_id,now()))
            geometry_valid=not structure_changed and (not prior_is_current or bool(previous['geometry_valid']))
            self.db.execute('''INSERT INTO table_edits(document_id,table_id,page,grid_json,verified,updated_at,geometry_valid,source_signature)
                        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(document_id,table_id)
                        DO UPDATE SET grid_json=excluded.grid_json,verified=excluded.verified,
                         updated_at=excluded.updated_at,geometry_valid=excluded.geometry_valid,
                         source_signature=excluded.source_signature''',
                        (doc_id, table_id, page,json_dump(grid),int(verified),now(),int(geometry_valid),signature))
            self.db.execute("UPDATE documents SET status='NEEDS_REVIEW',updated_at=? WHERE id=?", (now(),doc_id))
            self.audit(doc_id,'TABLE_EDIT',{'table_id':table_id,'page':page,
                                            'verified':verified,'structure_changed':structure_changed})

    def list_rules(self) -> list[dict]:
        return [dict(x) for x in self.db.execute("SELECT * FROM learning_rules ORDER BY created_at DESC")]

    def change_rule_state(self, rule_id: str, state: str):
        allowed = {'PROPOSED':{'REJECTED'},'TESTED':{'APPROVED','REJECTED'},
                   'APPROVED':{'ACTIVE','REJECTED'},'ACTIVE':{'DISABLED','ROLLED_BACK'},
                   'DISABLED':{'ACTIVE','ROLLED_BACK'}}
        with self.db:
            r = self.db.execute("SELECT state FROM learning_rules WHERE id=?",(rule_id,)).fetchone()
            if not r: raise KeyError(rule_id)
            if state not in allowed.get(r['state'], set()): raise ValueError(f"Không thể chuyển {r['state']} → {state}")
            self.db.execute("UPDATE learning_rules SET state=?,activated_at=? WHERE id=?",
                            (state,now() if state=='ACTIVE' else None,rule_id))
            self.audit(None,'RULE_STATE',{'id':rule_id,'old':r['state'],'new':state})

    def propose_suggestions(self, doc_id: str, field_key: str, current: str) -> list[dict]:
        """Never overwrite values; proposed alternatives for human review only."""
        document_type=self.get(doc_id)['document_type']
        rows=self.db.execute('''SELECT id,to_value,from_value FROM learning_rules
                     WHERE document_type=? AND field_key=? AND from_value=? AND state='ACTIVE' ''',
                     (document_type,field_key,current)).fetchall()
        return [{'rule_id':r['id'],'value':r['to_value'],'source':r['from_value']} for r in rows]


    def test_learning_rule(self,rule_id: str) -> tuple[bool,str]:
        """Conservative test on independent human-verified documents (not the training example)."""
        r=self.db.execute('SELECT * FROM learning_rules WHERE id=?',(rule_id,)).fetchone()
        if not r:raise KeyError(rule_id)
        if r['state']!='PROPOSED':
            return False,'Chỉ kiểm thử quy tắc ở trạng thái PROPOSED.'
        if r['field_key'].startswith('table:'):
            return False,'Quy tắc ô bảng chưa có tập kiểm thử độc lập đủ chuẩn. Giữ ở trạng thái PROPOSED.'
        samples=self.db.execute('''SELECT f.document_id,f.raw_value,f.final_value,f.verified
                                   FROM fields f JOIN documents d ON d.id=f.document_id
                                   WHERE d.document_type=? AND f.field_key=? AND f.raw_value=?
                                   AND f.document_id<>(SELECT document_id FROM correction_events WHERE id=?)''',
                                   (r['document_type'],r['field_key'],r['from_value'],r['correction_id'])).fetchall()
        eligible=[x for x in samples if x['verified']==1]
        matches=sum(x['final_value']==r['to_value'] for x in eligible)
        conflicts=len(eligible)-matches
        metrics={'holdout_count':len(eligible),'matches':matches,'conflicts':conflicts,'criterion':'3 independent verified docs, 0 conflict'}
        if len(eligible)<3 or conflicts:
            return False,(f'Chưa đạt: {len(eligible)} chứng từ đã duyệt độc lập; '
                          f'{matches} khớp, {conflicts} xung đột. Cần ≥3 chứng từ, không xung đột.')
        with self.db:
            self.db.execute("UPDATE learning_rules SET state='TESTED',quality_json=? WHERE id=?",(json_dump(metrics),rule_id))
            self.audit(None,'RULE_TEST_PASS',{'id':rule_id,'metrics':metrics})
        return True,f'Đạt kiểm thử: {len(eligible)} chứng từ độc lập, {matches} khớp, không xung đột.'

    def backup(self, target: Path):
        target.parent.mkdir(parents=True,exist_ok=True)
        destination = sqlite3.connect(str(target))
        try:
            self.db.backup(destination)
        finally:
            destination.close()

    def close(self):
        self.db.close()

    def list_templates(self) -> list[dict]:
        return [dict(r) for r in self.db.execute('SELECT * FROM templates ORDER BY name')]

    def save_template(self, spec: dict):
        from .templates import validate_template
        validate_template(spec)
        with self.db:
            self.db.execute('''INSERT INTO templates(id,name,document_type,spec_json,updated_at)
                            VALUES(?,?,?,?,?) ON CONFLICT(id)
                            DO UPDATE SET name=excluded.name,document_type=excluded.document_type,
                             spec_json=excluded.spec_json,updated_at=excluded.updated_at''',
                            (spec['id'],spec['name'],spec['document_type'],json_dump(spec),now()))
            self.audit(None,'TEMPLATE_SAVED',{'id':spec['id'],'name':spec['name']})

    def change_document_type(self, doc_id: str, document_type: str):
        if not document_type or len(document_type)>50 or not all(c.isalnum() or c=='_' for c in document_type):
            raise ValueError('Loại chứng từ không hợp lệ')
        with self.db:
            self.db.execute('UPDATE documents SET document_type=?,updated_at=? WHERE id=?',(document_type,now(),doc_id))
            self.audit(doc_id,'DOCUMENT_TYPE',{'new':document_type})

    def add_field(self, doc_id: str, label: str, value: str, page: int=0, bbox=None) -> str:
        if not label.strip():raise ValueError('Phải nhập tên trường')
        key='custom_'+uuid.uuid4().hex[:12]
        with self.db:
            self.db.execute('''INSERT INTO fields(document_id,field_key,label,raw_value,final_value,page,bbox_json,verified)
                     VALUES (?,?,?,?,?,?,?,0)''',(doc_id,key,label.strip(),value,value,page,json_dump(bbox)))
            d=self.get(doc_id)
            if d['last_result_json']:
                result=json.loads(d['last_result_json'])
                result['fields'].append(Field(key,label,value,value,page,bbox).to_dict())
                self.db.execute('UPDATE documents SET last_result_json=?,status=? WHERE id=?',(json_dump(result),'NEEDS_REVIEW',doc_id))
            self.audit(doc_id,'ADD_FIELD',{'key':key,'label':label})
        return key

    def verified_table_ids(self,doc_id: str) -> set[str]:
        d=self.get(doc_id)
        if not d['last_result_json']:return set()
        raw=json.loads(d['last_result_json'])
        current={t['table_id']:table_layout_signature(t) for page in raw.get('pages',[])
                 for t in page.get('tables',[])}
        return {r['table_id'] for r in self.db.execute(
            'SELECT table_id,source_signature FROM table_edits WHERE document_id=? AND verified=1 AND geometry_valid=1',(doc_id,))
            if r['source_signature']==current.get(r['table_id'])}