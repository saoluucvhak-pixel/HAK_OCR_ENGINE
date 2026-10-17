"""PaddleOCR 3.x basic text-recognition adapter, loaded lazily."""
from ..core import OCRPage

class PaddleAdapter:
    name = "paddle"
    def __init__(self, model=None):
        self._model = model
    def _get_model(self):
        if self._model is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError("Install PaddleOCR separately for this adapter") from exc
            self._model = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                                    use_textline_orientation=False)
        return self._model
    def recognize(self, image_paths):
        model = self._get_model()
        output = []
        for i, path in enumerate(image_paths, 1):
            predictions = model.predict(str(path))
            text_lines = []
            scores = []
            for prediction in predictions:
                info = prediction.json if hasattr(prediction, "json") else prediction
                if callable(info): info = info()
                data = info.get("res", info)
                text_lines.extend(str(x) for x in data.get("rec_texts", []))
                scores.extend(float(x) for x in data.get("rec_scores", []))
            output.append(OCRPage(number=i, text="\n".join(text_lines),
                                  confidence=sum(scores) / len(scores) if scores else None))
        return output
