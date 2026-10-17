"""HAK OCR CLI — opt-in engines, no automatic model downloads by HAK."""
import argparse
import json
from pathlib import Path
from .core import OCRService
from .adapters import PaddleAdapter, UnlimitedAdapter

def main(argv=None):
    p = argparse.ArgumentParser(description="HAK OCR Engine")
    p.add_argument("file", type=Path)
    p.add_argument("--engine", choices=("paddle", "unlimited"), required=True)
    p.add_argument("--out", type=Path)
    p.add_argument("--endpoint", default="http://127.0.0.1:10000")
    args = p.parse_args(argv)
    engines = {"paddle": PaddleAdapter(), "unlimited": UnlimitedAdapter(endpoint=args.endpoint)}
    data = OCRService(engines).process(args.file, args.engine).to_dict()
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

if __name__ == "__main__": main()
