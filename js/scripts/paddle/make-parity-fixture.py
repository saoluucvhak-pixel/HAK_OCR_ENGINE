"""Sinh đáp án đối chiếu cho js/main/paddle-rec.js từ CHÍNH thư viện gốc (cv2 + PaddleX OCRReisizeNormImg + PaddleOCR TextRecognition).
python make-parity-fixture.py <crops.jsonl> <ra: parity.json>
crops.jsonl: mỗi dòng {id, src, w, h, data (base64 xám)} — ô do app cắt ra (ảnh mẫu giả lập, không có dữ liệu thật).
Cần: paddleocr 3.x, paddlex, opencv. Model latin_PP-OCRv5_mobile_rec tự tải lần đầu."""
import base64, json, os, sys
os.environ.setdefault('DISABLE_MODEL_SOURCE_CHECK', 'True')
import cv2, numpy as np
from paddlex.inference.models.text_recognition.processors import OCRReisizeNormImg
from paddleocr import TextRecognition

src, out = sys.argv[1], sys.argv[2]
b64 = lambda a: base64.b64encode(np.ascontiguousarray(a, np.uint8).tobytes()).decode()
rng = np.random.default_rng(3)

# 1) Đổi cỡ: phóng to, thu nhỏ, tỷ lệ lẻ, ảnh 1 điểm cao / rộng
resize = []
for w, h, dw, dh in [(37, 21, 84, 48), (400, 90, 214, 48), (9, 48, 9, 48), (123, 61, 97, 48), (1, 30, 2, 48), (60, 1, 2880, 48)]:
    a = rng.integers(0, 256, (h, w), dtype=np.uint8)
    resize.append({'w': w, 'h': h, 'dw': dw, 'dh': dh, 'src': b64(a), 'cv2': b64(cv2.resize(a, (dw, dh)))})

# 2) Tiền xử lý đầy đủ + 3) nhận dạng: lấy đều các nguồn ảnh
rows = [json.loads(l) for l in open(src, encoding='utf-8')]
pick, seen = [], {}
for r in rows:
    if seen.get(r['src'], 0) < 4: pick.append(r); seen[r['src']] = seen.get(r['src'], 0) + 1
norm, rec = OCRReisizeNormImg(), TextRecognition(model_name='latin_PP-OCRv5_mobile_rec', enable_mkldnn=False)
pre, recog = [], []
for r in pick:
    g = np.frombuffer(base64.b64decode(r['data']), np.uint8).reshape(r['h'], r['w'])
    bgr = np.ascontiguousarray(np.stack([g, g, g], -1))
    t = norm([bgr])[0]                                             # [3, 48, W] float, (x/255 − 0,5)/0,5
    item = {'id': r['id'], 'w': r['w'], 'h': r['h'], 'data': r['data']}
    if len(pre) < 6: pre.append(dict(item, dims=list(t.shape), ch0=b64(np.rint(t[0] * 127.5 + 127.5))))   # kênh 0 quy về 0–255
    p = rec.predict(input=bgr, batch_size=1)[0]
    recog.append(dict(item, text=p['rec_text'], score=float(p['rec_score'])))
json.dump({'note': 'Đáp án sinh bằng cv2 ' + cv2.__version__ + ' + PaddleX OCRReisizeNormImg + latin_PP-OCRv5_mobile_rec (paddle_static). Ảnh ô từ ảnh mẫu giả lập.',
           'resize': resize, 'preprocess': pre, 'recognize': recog}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print('resize', len(resize), 'preprocess', len(pre), 'recognize', len(recog))
