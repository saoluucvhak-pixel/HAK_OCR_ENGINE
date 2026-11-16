"""Portable backups: SQLite snapshot plus original files, no runtime/user secrets."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
import json
import shutil
import sqlite3
from datetime import datetime,timezone


def sha_file(path: Path):
    h=sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def backup_complete(repo, out:Path):
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as tmp:
        db=Path(tmp)/'hak_ocr.sqlite3'
        repo.backup(db)
        files=[db]
        originals=sorted((repo.home/'originals').glob('*'))
        files.extend(x for x in originals if x.is_file())
        manifest={'version':1,'created_at':datetime.now(timezone.utc).isoformat(),'files':{}}
        with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=6) as z:
            for src in files:
                name='hak_ocr.sqlite3' if src==db else 'originals/'+src.name
                manifest['files'][name]=sha_file(src)
                z.write(src,name)
            z.writestr('manifest.json',json.dumps(manifest,indent=2))
    return out


def restore_complete(bundle: Path,destination: Path):
    """Restore only to a NEW/EMPTY directory. Never overwrite current user work."""
    bundle=Path(bundle);destination=Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Chỉ phục hồi vào một thư mục dữ liệu trống để tránh ghi đè')
    with ZipFile(bundle,'r') as z:
        if 'manifest.json' not in z.namelist():raise ValueError('Thiếu manifest')
        meta=json.loads(z.read('manifest.json'))
        if meta.get('version')!=1:raise ValueError('Định dạng sao lưu chưa được hỗ trợ')
        all_files=meta['files']
        if 'hak_ocr.sqlite3' not in all_files:raise ValueError('Thiếu CSDL')
        for name,digest in all_files.items():
            # Only approved relative paths; disallow traversal, symlinks, arbitrary files.
            name_obj=Path(name)
            if (name != 'hak_ocr.sqlite3' and not (len(name_obj.parts)==2 and name_obj.parts[0]=='originals')) or '..' in name_obj.parts:
                raise ValueError('Đường dẫn trong bản sao lưu không hợp lệ')
            raw=z.read(name)
            if sha256(raw).hexdigest()!=digest:raise ValueError(f'Checksum lỗi: {name}')
        destination.mkdir(parents=True,exist_ok=True)
        for name in all_files:
            target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('wb') as f:f.write(z.read(name))
    # Re-point stored absolute paths on the original machine to the new data home.
    with sqlite3.connect(str(destination/'hak_ocr.sqlite3')) as db:
        rows=db.execute('SELECT id,original_path FROM documents').fetchall()
        for docid,old in rows:
            ext=Path(old).suffix
            local=destination/'originals'/(docid+ext)
            if not local.is_file():raise ValueError('Thiếu tài liệu sau phục hồi: '+docid)
            db.execute('UPDATE documents SET original_path=? WHERE id=?',(str(local),docid))
        db.commit()
    return destination
