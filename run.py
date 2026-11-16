"""Windows GUI entry point; --self-test writes a JSON diagnostics file."""
from __future__ import annotations
import sys


def main():
    if '--self-test' in sys.argv:
        from pathlib import Path
        import json
        from hak_ocr.selftest import check_packaged_app
        pos = sys.argv.index('--self-test')
        if pos + 1 >= len(sys.argv):
            return 2
        destination=Path(sys.argv[pos+1])
        require_bundled='--require-bundled' in sys.argv
        report=check_packaged_app(require_bundled=require_bundled)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        return 0 if report['ok'] else 1
    from hak_ocr.gui import main as launch
    return launch()

if __name__ == '__main__':
    raise SystemExit(main())
