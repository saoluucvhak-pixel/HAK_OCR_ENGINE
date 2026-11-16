"""Conservative, source-linked attendance interpretation.

Works on already extracted (and possibly user reviewed) table grids.
Never turns a blank into zero or approves an attendance adjustment.
"""
from __future__ import annotations
import re
from calendar import monthrange
from .validation import fold_vietnamese, parse_attendance_value


def _text(value) -> str:
    return fold_vietnamese(str(value or '')).strip()


def _total(value):
    s=str(value or '').strip()
    return float(s.replace(',','.')) if re.fullmatch(r'\d{1,5}(?:[.,]\d{1,2})?',s) else None


def _day(value):
    s=str(value or '').strip()
    if re.fullmatch(r'0?[1-9]|[12]\d|3[01]',s):return int(s)
    return None


def _month(pages):
    text='\n'.join(p.get('text','')[:3000] for p in pages)
    m=re.search(r'(?i)th[aá]ng\s*0?([1-9]|1[012])\s*(?:[/\-]|n[aă]m\s*)\s*(20\d\d)',text)
    if m:return f'{int(m.group(1)):02d}/{m.group(2)}'
    return None


def _bbox(table,ri,ci):
    boxes=table.get('cell_boxes') or []
    if ri<len(boxes) and ci<len(boxes[ri]):return boxes[ri][ci]
    return None


def _total_row_name(s):
    norm=_text(s).replace(' ','')
    return norm in {'tc','tong','tongcong','cong','total','tongcom'}


def _vertical(table,period):
    grid=table.get('grid',[])
    if not grid or min(map(len,grid))<3 or len(grid)<12:return None
    headers=[_text(x) for x in grid[0][:4]]
    if not ('ngay' in headers[0] or headers[0]=='date'):return None
    if 'cong' not in ' '.join(headers[1:]) and 'com' not in ' '.join(headers[1:]):return None
    # A row number alone is not sufficient. Anchor against sequential labels.
    body=grid[1:]
    day_indices=[(i,_day(row[0])) for i,row in enumerate(body) if row]
    labelled=[(i,d) for i,d in day_indices if d is not None]
    sequential=sum(1 for i,d in labelled if d==i+1)
    if sequential<max(5,min(12,len(body)//3)):
        return {'kind':'vertical_daily','verified':False,'period':period,'records':[],
                'issues':['Không đọc đủ nhãn ngày để ánh xạ dữ liệu; cần chỉnh sửa ô ngày trên ảnh.']}
    rows=[];issues=[]
    max_day=31
    if period:
        try:
            month,year=map(int,period.split('/'))
            max_day=monthrange(year,month)[1]
        except (ValueError,IndexError):pass
    for idx,row in enumerate(body):
        if not row:continue
        if _total_row_name(row[0]):
            totals={headers[c] if c<len(headers) else f'cot_{c+1}':_total(row[c]) for c in range(1,len(row))}
            continue
        raw_day=_day(row[0]);day=raw_day;inferred=False
        # This layout has a strongly anchored DAILY sequential row pattern.
        # Do not assign an obviously misread '2' to day 6: keep the original
        # reading and mark the proposed calendar day explicitly unverified.
        if idx<max_day and raw_day!=idx+1:
            day=idx+1;inferred=True
            issues.append(f'Dòng {idx+2}: OCR nhãn ngày «{row[0]}», đề xuất ngày {day}; phải đối chiếu ảnh gốc.')
        if day is None or day<1 or day>max_day:
            if idx>=max_day:
                issues.append(f'Dòng {idx+2}: nằm ngoài tháng {period or "không xác định"}; có thể là dòng tổng, phải kiểm tra nhãn và ô tổng.')
            else:
                issues.append(f'Dòng {idx+2}: nhãn ngày không hợp lệ');
            continue
        for ci in range(1,len(row)):
            label=headers[ci] if ci<len(headers) else f'cot_{ci+1}'
            val=parse_attendance_value(row[ci])
            if row[ci].strip() and val is None:
                issues.append(f'Ngày {day}, {label}: ký tự không hợp lệ «{row[ci]}»')
            rows.append({'person':None,'day':day,'metric':label,'raw':row[ci],
                         'value':val,'inferred_day':inferred,'bbox':_bbox(table,idx+1,ci),
                         'day_raw':str(row[0]),'reviewed':bool(table.get('verified')) and not inferred})
    if 'totals' not in locals():totals={}
    for key,claimed in totals.items():
        vals=[r['value'] for r in rows if r['metric']==key]
        complete=all(v is not None for v in vals)
        if claimed is not None and complete and abs(sum(vals)-claimed)>.001:
            issues.append(f'Tổng {key}: các ô là {sum(vals):g}, cuối bảng ghi {claimed:g}')
        elif claimed is not None and not complete:
            issues.append(f'Tổng {key}={claimed:g}: còn ô trống/chưa đọc, KHÔNG coi như số 0')
    return {'kind':'vertical_daily','period':period,'verified':bool(table.get('verified')),
            'records':rows,'printed_totals':totals,'issues':issues}


def _horizontal(table,period):
    grid=table.get('grid',[])
    if len(grid)<2:return None
    best=None
    for ri,row in enumerate(grid[:6]):
        days={ci:_day(v) for ci,v in enumerate(row) if _day(v) is not None}
        # At least five successive adjacent columns representing increasing days.
        consecutive=sum(1 for ci,day in days.items() if days.get(ci+1)==day+1)
        if consecutive>=4 and (best is None or consecutive>best[0]):best=(consecutive,ri,days)
    if not best:return None
    _,head,days=best
    rows=[];issues=[]
    header_label=' '.join(' '.join(r[:min(days)]) for r in grid[max(0,head-2):head+1])
    if not any(k in _text(header_label) for k in ('ho va ten','ho ten','nhan vien','chuc vu')):
        # Some printed schedules have only a list of names; keep them but mark unconfirmed.
        issues.append('Chưa xác định chắc chắn cột Họ và tên; kiểm tra lại danh sách nhân viên.')
    first_day_col=min(days)
    person_col=first_day_col-1
    header_text=' '.join(str(v) for v in grid[head]).lower()
    if len(set(days.values()))<5:return None
    for ri in range(head+1,len(grid)):
        row=grid[ri]
        if person_col>=len(row):continue
        person=str(row[person_col]).strip()
        if not person or _total_row_name(person) or person.isdigit():continue
        for ci,day in sorted(days.items()):
            if ci>=len(row):continue
            raw=str(row[ci]).strip();value=parse_attendance_value(raw)
            if raw and value is None:issues.append(f'{person}, ngày {day}: «{raw}» cần soát xét')
            rows.append({'person':person,'day':day,'metric':'cong','raw':raw,
                         'value':value,'bbox':_bbox(table,ri,ci),
                         'reviewed':bool(table.get('verified')),'inferred_day':False})
    return {'kind':'horizontal_daily','period':period,'verified':bool(table.get('verified')),
            'records':rows,'printed_totals':{},'issues':issues}


def analyse_attendance(result: dict) -> list[dict]:
    period=_month(result.get('pages',[]));output=[]
    for page in result.get('pages',[]):
        for table in page.get('tables',[]):
            analysed=_vertical(table,period) or _horizontal(table,period)
            if analysed:
                analysed.update({'page':page['number'],'table_id':table['table_id']})
                if not analysed['verified']:
                    analysed['issues'].insert(0,'Bảng chưa được người dùng xác nhận; không dùng để tính lương.')
                output.append(analysed)
    return output
