from __future__ import annotations
import re
import unicodedata


def fold_vietnamese(text: str) -> str:
    decomp=unicodedata.normalize('NFD',text)
    return ''.join(ch for ch in decomp if unicodedata.category(ch)!='Mn').replace('đ','d').replace('Đ','D').casefold()


def parse_attendance_value(text: str):
    """Only explicit, unambiguous non-negative numeric attendance cells.

    Blank is None, NEVER zero. Both comma and dot decimal separators accepted,
    while thousands syntax and OCR artifacts are refused in this context.
    """
    cleaned=str(text).strip()
    if not cleaned or cleaned in ('-','—','–'):return None
    if not re.fullmatch(r'\d{1,2}(?:[.,]\d{1,2})?',cleaned):return None
    n=float(cleaned.replace(',','.'))
    return n if 0<=n<=24 else None


def validate_attendance_grid(grid: list[list[str]]) -> list[dict]:
    """Conservative check ONLY if unambiguous day header and total column are present."""
    if len(grid)<3:return []
    header=None;days=[];total_col=None
    for ri,row in enumerate(grid[:5]):
        mapped={}
        for ci,v in enumerate(row):
            token=str(v).strip()
            if token.isdigit() and 1<=int(token)<=31:
                mapped[ci]=int(token)
        if len(mapped)>=5 and len(set(mapped.values()))==len(mapped):
            header=ri;days=list(mapped)
            for ci,v in enumerate(row):
                folded=fold_vietnamese(str(v)).replace(' ','')
                if folded in ('tc','tongcong','cong','tcong') and ci not in days:total_col=ci
            break
    if header is None or total_col is None:return []
    issues=[]
    for ri,row in enumerate(grid[header+1:],start=header+1):
        if total_col>=len(row):continue
        total=parse_attendance_value(row[total_col])
        if total is None:continue
        values=[parse_attendance_value(row[ci]) for ci in days if ci<len(row)]
        if not any(v is not None for v in values):continue
        computed=sum(v for v in values if v is not None)
        if abs(computed-total)>0.01:
            issues.append({'row':ri+1,'severity':'REVIEW',
                           'message':f'Tổng cột ngày {computed:g} khác TC {total:g}',
                           'computed':computed,'printed':total})
    return issues
