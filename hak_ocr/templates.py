from __future__ import annotations
import re
from .models import Field, Page


DEFAULT_ATTENDANCE_TEMPLATE={
    'id':'attendance-basic-v1',
    'name':'Bảng chấm công — thông tin kỳ',
    'document_type':'bang_cham_cong',
    'fields':[
        {'key':'ky_cham_cong','label':'Kỳ chấm công',
         'pattern':r'(?i)th[aá]ng\s*(\d{1,2}\s*(?:[/\-]\s*20\d{2}|n[aă]m\s+20\d{2}))',
         'group':1}
    ]
}


def validate_template(spec: dict):
    if not isinstance(spec,dict) or not all(k in spec for k in ('id','name','document_type','fields')):
        raise ValueError('Template thiếu id, name, document_type hoặc fields')
    if not isinstance(spec['fields'],list) or len(spec['fields'])>60:
        raise ValueError('Số lượng fields vượt giới hạn')
    for item in spec['fields']:
        if not all(k in item for k in ('key','label','pattern')):
            raise ValueError('Mỗi field phải có key,label,pattern')
        pattern=item['pattern']
        if not isinstance(pattern,str) or len(pattern)>250:
            raise ValueError('Biểu thức pattern rỗng hoặc quá dài')
        re.compile(pattern)


def extract_template_fields(pages:list[Page],specs:list[dict],doc_type: str) -> list[Field]:
    fields=[]; used=set()
    for template in specs:
        validate_template(template)
        if template['document_type']!=doc_type:continue
        for fld in template['fields']:
            if fld['key'] in used:continue
            pattern=re.compile(fld['pattern'],re.IGNORECASE)
            for page in pages:
                match=pattern.search(page.text[:200_000])
                if not match:continue
                group=fld.get('group',1)
                try:value=match.group(group)
                except IndexError: value=match.group(0)
                value=str(value).strip()
                word=next((v for v in page.blocks if v.text.strip('.,:')==value.strip('.,:')),None)
                fields.append(Field(fld['key'],fld['label'],value,value,page.number,
                                    word.bbox if word else None,word.confidence if word else None,
                                    False,'template:'+template['id'],template['id']))
                used.add(fld['key']);break
    return fields
