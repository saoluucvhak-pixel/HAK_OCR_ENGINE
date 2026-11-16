"""No-GUI smoke test / offline CLI. Example:
python cli.py check
python cli.py import-and-ocr myfile.jpg --data ./data
python cli.py export <document-id> --format xlsx --data ./data
"""
from __future__ import annotations
import argparse
from pathlib import Path
from hak_ocr.processing import check_ocr_ready, process_file
from hak_ocr.storage import Repository
from hak_ocr.exporting import export_result
from hak_ocr.backup import backup_complete,restore_complete
from hak_ocr.advanced_engines import engine_report, DocUnwarpLocal
from hak_ocr.evidence_ai import extract_evidence_claims, LocalGGUFExtractor
from hak_ocr.handwriting import HandwritingLocal


def main():
    parser=argparse.ArgumentParser(description='HAK Smart OCR AI - offline CLI')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    sub.add_parser('advanced-check')
    off=sub.add_parser('office',help='Word/Excel/PowerPoint/HTML/CSV -> Markdown (MarkItDown, offline)')
    off.add_argument('file',type=Path)
    off.add_argument('--out',type=Path,help='Ghi Markdown ra file thay vì in ra màn hình')
    off.add_argument('--json',action='store_true',help='In JSON (source, kind, sha256, markdown)')
    uo=sub.add_parser('unlimited-ocr',help='Optional Unlimited-OCR on one image (local GPU model)')
    uo.add_argument('image',type=Path,nargs='?')
    uo.add_argument('--models-dir',type=Path)
    uo.add_argument('--check',action='store_true',help='Chỉ kiểm tra model/thư viện/GPU')
    claims=sub.add_parser('evidence-claims')
    claims.add_argument('document_id');claims.add_argument('--data',type=Path)
    claims.add_argument('--llm',action='store_true',help='Optional GGUF model installed in vendor/models/evidence_llm')
    warp=sub.add_parser('unwarp-preview')
    warp.add_argument('input',type=Path);warp.add_argument('output',type=Path)
    warp.add_argument('--models-dir',type=Path)
    htr=sub.add_parser('handwriting')
    htr.add_argument('crop',type=Path,help='Crop of handwritten text, preferably one line')
    htr.add_argument('--models-dir',type=Path)
    back=sub.add_parser('backup')
    back.add_argument('file',type=Path)
    back.add_argument('--data',type=Path)
    restore=sub.add_parser('restore')
    restore.add_argument('file',type=Path)
    restore.add_argument('--to',type=Path,required=True)
    ing=sub.add_parser('import-and-ocr')
    ing.add_argument('file',type=Path)
    ing.add_argument('--data',type=Path)
    ing.add_argument('--no-rotation',action='store_true')
    ing.add_argument('--no-tables',action='store_true')
    ing.add_argument('--deep-cells',action='store_true',help='Slow per-cell numeric OCR')
    ing.add_argument('--engine',choices=['tesseract','paddle','hybrid'],default='tesseract')
    ing.add_argument('--docling',action='store_true',help='PDF layout enrichment, local models only')
    ing.add_argument('--perspective',action='store_true',help='Conservative planar document rectification')
    ing.add_argument('--models-dir',type=Path,help='Offline model directory')
    exp=sub.add_parser('export')
    exp.add_argument('document_id')
    exp.add_argument('--format',choices=['xlsx','json','txt','csv'],default='xlsx')
    exp.add_argument('--data',type=Path)
    args=parser.parse_args()
    if args.command=='check':
        print('Offline OCR language:',check_ocr_ready());return
    if args.command=='advanced-check':
        import json
        print(json.dumps(engine_report(),ensure_ascii=False,indent=2));return
    if args.command=='office':
        import json
        from hak_ocr.office import convert_office
        res=convert_office(args.file)
        if args.json:print(json.dumps(res.to_dict(),ensure_ascii=False,indent=2));return
        if args.out:
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(res.markdown+'\n',encoding='utf-8');print(args.out);return
        print(res.markdown);return
    if args.command=='unlimited-ocr':
        import json
        from hak_ocr.unlimited_engine import unlimited_status, UnlimitedOCRLocal
        if args.check or not args.image:
            print(json.dumps(unlimited_status(args.models_dir),ensure_ascii=False,indent=2));return
        from PIL import Image
        with Image.open(args.image) as im:
            print('UNVERIFIED OCR (manual review):');print(UnlimitedOCRLocal(args.models_dir).read(im))
        return
    if args.command=='unwarp-preview':
        from PIL import Image
        with Image.open(args.input) as im:
            out=DocUnwarpLocal(args.models_dir).unwarp(im)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        out.save(args.output)
        print('UNVERIFIED DERIVATIVE (manual review):',args.output)
        return
    if args.command=='handwriting':
        from PIL import Image
        import json
        with Image.open(args.crop) as image:
            candidate=HandwritingLocal(args.models_dir).recognize(image)
        print(json.dumps(candidate,ensure_ascii=False,indent=2));return
    if args.command=='restore':
        print('Restored to:',restore_complete(args.file,args.to));return
    with_repository=Repository(args.data)
    try:
        if args.command=='backup':
            print('Backup:',backup_complete(with_repository,args.file))
        elif args.command=='evidence-claims':
            import json
            result=with_repository.get_result(args.document_id)
            if not result:raise ValueError('Tài liệu chưa có OCR')
            text='\n'.join(p.get('text','') for p in result['pages'])
            claims=(LocalGGUFExtractor().extract(text) if args.llm else extract_evidence_claims(text))
            ids=with_repository.add_evidence_claims(args.document_id,claims,run_id=result.get('run_id'))
            print(json.dumps({'count':len(ids),'claims':claims},ensure_ascii=False,indent=2))
        elif args.command=='import-and-ocr':
            doc_id,new=with_repository.add_file(args.file)
            source=with_repository.get(doc_id)
            result=process_file(source['original_path'],doc_id,source['sha256'],
                                detect_rotation=not args.no_rotation,tables=not args.no_tables,
                                deep_cells=args.deep_cells,ocr_engine=args.engine,
                                docling_enabled=args.docling,auto_perspective=args.perspective,
                                models_dir=args.models_dir,
                                progress=lambda i,n:print(f'Page {i}/{n}'))
            with_repository.save_result(result)
            print('DOCUMENT_ID',doc_id)
            print('STATUS',result.status,'TYPE',result.document_type)
            print('PAGES',len(result.pages),'TABLES',sum(len(x.tables) for x in result.pages))
            print('OCR TEXT PREVIEW:',result.pages[0].text[:350] if result.pages else '')
        else:
            result=with_repository.get_result(args.document_id)
            if not result:raise RuntimeError('Chưa có dữ liệu OCR cho mã tài liệu')
            path=with_repository.home/'exports'/f'{args.document_id}.{args.format}'
            export_result(result,path);print(path)
    finally:with_repository.close()

if __name__=='__main__':main()
