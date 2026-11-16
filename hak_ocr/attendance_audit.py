"""Offline, conservative reconciliation of OCR attendance cells.

Never turns missing cells into zeros and never authorizes payroll postings.
"""
from __future__ import annotations
from collections import defaultdict
import re
from .validation import parse_attendance_value


def audit_attendance(result: dict) -> list[dict]:
    """Return evidence-linked audit rows; summaries are not approvals."""
    output=[]
    for table in result.get('attendance_analysis', []):
        grouped=defaultdict(list)
        for record in table.get('records', []):
            grouped[(record.get('person') or '', record.get('metric') or '')].append(record)
        for (person,metric),records in grouped.items():
            valid=[r['value'] for r in records if isinstance(r.get('value'),(int,float))]
            blanks=[r for r in records if r.get('value') is None and not str(r.get('raw','')).strip()]
            invalid=[r for r in records if r.get('value') is None and str(r.get('raw','')).strip()]
            duplicate_days=len(set(r['day'] for r in records))!=len(records)
            inferred=[r for r in records if r.get('inferred_day')]
            flags=[]
            if blanks:flags.append(f'{len(blanks)} ô trống/chưa nhập; không thay thành 0')
            if invalid:flags.append(f'{len(invalid)} ô không đọc được')
            if duplicate_days:flags.append('Trùng nhãn ngày')
            if inferred:flags.append(f'{len(inferred)} ngày suy luận từ vị trí')
            if not table.get('verified'):flags.append('Bảng chưa được duyệt')
            output.append({
                'table_id':table.get('table_id',''), 'page':int(table.get('page',0)),
                'period':table.get('period'), 'person':person or None,'metric':metric,
                'read_sum':round(sum(valid),4),'numeric_cells':len(valid),
                'blank_cells':len(blanks),'invalid_cells':len(invalid),
                'expected_cells':len(records), 'verified':bool(table.get('verified')),
                'requires_review':bool(flags), 'warnings':flags,
                'source_boxes':[{'day':r['day'],'bbox':r.get('bbox'),'raw':r.get('raw','')}
                                for r in records],
                'payroll_ready':False,  # manual cross-document reconciliation required
            })
    return output
