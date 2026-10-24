"""HAK OCR CLI — opt-in engines, no automatic model downloads by HAK."""
import argparse
import json
from pathlib import Path
from .core import OCRService
from .adapters import PaddleAdapter, UnlimitedAdapter, SmartOCRAdapter

def main(argv=None):
    p = argparse.ArgumentParser(description="HAK OCR Engine")
    p.add_argument("file", type=Path)
    p.add_argument("--engine", choices=("paddle", "unlimited", "hak-smart"), required=True)
    p.add_argument("--out", type=Path)
    p.add_argument("--paddle-mode", choices=("text", "structure"), default="text")
    p.add_argument("--endpoint", default="http://127.0.0.1:10000")
    p.add_argument("--smart-app-dir", type=Path, help="Path to existing HAK Smart OCR AI app")
    p.add_argument("--smart-engine", choices=("tesseract", "paddle", "hybrid"), default="tesseract")
    args = p.parse_args(argv)
    engines = {"paddle": PaddleAdapter(mode=args.paddle_mode), "unlimited": UnlimitedAdapter(endpoint=args.endpoint)}
    if args.engine == "hak-smart":
        if args.smart_app_dir is None:
            p.error("--smart-app-dir is required for --engine hak-smart")
        engines["hak-smart"] = SmartOCRAdapter(args.smart_app_dir, ocr_engine=args.smart_engine)
    data = OCRService(engines).process(args.file, args.engine).to_dict()
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

if __name__ == "__main__": main()
