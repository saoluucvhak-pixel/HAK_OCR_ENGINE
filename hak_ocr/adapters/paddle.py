"""PaddleOCR 3.x adapter: OCR text or PP-StructureV3 document parsing.

The two official pipelines are optional dependencies. Models must be provisioned
locally for strictly offline operation; no implicit claim that defaults stay offline.
"""
from __future__ import annotations
from html.parser import HTMLParser
from ..core import OCRPage


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell, self.in_cell = [], None, [], False
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.in_cell, self.cell = True, []
    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.row.append("".join(self.cell).strip())
            self.in_cell = False
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def html_table_grid(html: str) -> list[list[str]]:
    """Extract simple table cells; merged-cell geometry is not reconstructed."""
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def _result_dict(value):
    data = value.json if hasattr(value, "json") else value
    if callable(data):
        data = data()
    if not isinstance(data, dict):
        raise ValueError("Unexpected PaddleOCR result shape")
    return data.get("res", data)


class PaddleAdapter:
    name = "paddle"
    def __init__(self, model=None, *, mode="text", model_options=None):
        if mode not in ("text", "structure"):
            raise ValueError("Paddle mode must be text or structure")
        self._model = model
        self.mode = mode
        self.model_options = dict(model_options or {})

    def _get_model(self):
        if self._model is None:
            try:
                if self.mode == "structure":
                    from paddleocr import PPStructureV3
                    self._model = PPStructureV3(**self.model_options)
                else:
                    from paddleocr import PaddleOCR
                    options = {"use_doc_orientation_classify": False,
                               "use_doc_unwarping": False,
                               "use_textline_orientation": False}
                    options.update(self.model_options)
                    self._model = PaddleOCR(**options)
            except ImportError as exc:
                raise RuntimeError("Install PaddleOCR 3.x with matching PaddlePaddle runtime") from exc
        return self._model

    def recognize(self, image_paths):
        model = self._get_model()
        output = []
        for number, path in enumerate(image_paths, 1):
            predicted = model.predict(str(path))
            lines, scores, tables = [], [], []
            for raw in predicted:
                data = _result_dict(raw)
                if self.mode == "structure":
                    blocks = data.get("parsing_res_list", [])
                    for block in blocks:
                        if not isinstance(block, dict):
                            continue
                        text = str(block.get("block_content") or "").strip()
                        if text:
                            lines.append(text)
                    for table in data.get("table_res_list", []):
                        if isinstance(table, dict) and isinstance(table.get("pred_html"), str):
                            tables.append(html_table_grid(table["pred_html"]))
                    # Some versions provide only overall OCR results.
                    if not lines:
                        lines.extend(str(s) for s in data.get("overall_ocr_res", {}).get("rec_texts", []))
                else:
                    lines.extend(str(s) for s in data.get("rec_texts", []))
                    scores.extend(float(s) for s in data.get("rec_scores", []) if s is not None)
            output.append(OCRPage(number=number, text="\n".join(lines),
                                  confidence=sum(scores) / len(scores) if scores else None,
                                  tables=tables))
        return output
