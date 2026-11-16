"""Benchmark one LOCAL OCR sample against separately confirmed cells.

Run from project root:
  python scripts/benchmark_table.py picture.jpg validation/example_schedule_reference.json --no-rotation
The expected-file example is provisional visual transcription, NOT payroll approval.
Image bytes and names are never included in the distributable benchmark file.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from hak_ocr.processing import process_file


def main():
    p=argparse.ArgumentParser()
    p.add_argument('image',type=Path)
    p.add_argument('truth',type=Path)
    p.add_argument('--no-rotation',action='store_true')
    args=p.parse_args()
    expected=json.loads(args.truth.read_text(encoding='utf-8'))
    data=process_file(args.image,'benchmark-not-persisted','benchmark',
                      detect_rotation=not args.no_rotation,deep_cells=True).to_dict()
    pages=data.get('pages',[])
    tables=[t for page in pages for t in page.get('tables',[])]
    idx=expected.get('table_index',0)
    if len(tables)<=idx:
        print('TABLE_NOT_FOUND, benchmark failed',file=sys.stderr)
        return 2
    table=tables[idx]
    correct=0;failures=[]
    for entry in expected['cells']:
        ri,ci=int(entry['row']),int(entry['col'])
        predicted=(table['grid'][ri][ci] if ri<len(table['grid']) and ci<len(table['grid'][ri]) else None)
        if predicted==entry['expected']:correct+=1
        else:failures.append({'row':ri,'col':ci,'expected':entry['expected'],'predicted':predicted})
    report={
        'method':'exact-cell-match',
        'source_data_verified':False,
        'description':'Benchmark against manually supplied provisional labels, not business verification.',
        'matches':correct,'total':len(expected['cells']),
        'accuracy':round(correct/max(1,len(expected['cells'])),4),
        'grid_shape':[len(table['grid']),max((len(x) for x in table['grid']),default=0)],
        'header_read':table['grid'][0] if table['grid'] else [],
        'ocr_suggestions':len(table.get('cell_suggestions',[])),
        'failures':failures,
    }
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not failures else 1

if __name__=='__main__':raise SystemExit(main())
