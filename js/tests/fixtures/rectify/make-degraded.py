"""Tạo các biến thể "ảnh chụp" từ ảnh mẫu bảng in, lưu dạng xám thô: 8 byte (w,h uint32 LE) + pixel."""
import io, struct, sys
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
base = Image.open(src).convert('L')

def gradient(img, strength):          # ánh sáng không đều: tối dần sang góc phải dưới
    a = np.asarray(img).astype(np.float32); h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]; g = 1 - strength * (xx / w * 0.6 + yy / h * 0.4)
    return Image.fromarray(np.clip(a * g, 0, 255).astype(np.uint8))

def shadow(img):                      # bóng tay/điện thoại đè một dải
    a = np.asarray(img).astype(np.float32).copy(); h, w = a.shape
    a[:, int(w * 0.55):int(w * 0.75)] *= 0.62
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def jpeg(img, q):
    b = io.BytesIO(); img.save(b, 'JPEG', quality=q); return Image.open(io.BytesIO(b.getvalue())).convert('L')

def rot(img, deg): return img.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor=255)
def scale(img, f): return img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
def skew(img, k, pad=60):               # phối cảnh kiểu camera (projective): cạnh trên của tờ giấy hẹp hơn cạnh dưới k·w
    img = Image.new('L', (img.width + 2 * pad, img.height + 2 * pad), 255); img.paste(base_for_skew[0], (pad, pad))
    w, h = img.size; d = w * k
    src = [(0, 0), (w, 0), (w, h), (0, h)]; dst = [(d, 0), (w - d, 0), (w, h), (0, h)]   # góc ảnh gốc → vị trí trên ảnh chụp
    A = []; B = []
    for (x, y), (X, Y) in zip(dst, src):     # hệ số PIL: ánh xạ điểm ảnh RA (X,Y chụp) → điểm ảnh VÀO
        A += [[x, y, 1, 0, 0, 0, -X * x, -X * y], [0, 0, 0, x, y, 1, -Y * x, -Y * y]]; B += [X, Y]
    coeffs = np.linalg.solve(np.array(A, float), np.array(B, float))
    return img.transform((w, h), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC, fillcolor=255)
base_for_skew = [base]
def noise(img, s, seed=1):
    a = np.asarray(img).astype(np.float32) + np.random.default_rng(seed).normal(0, s, (img.height, img.width))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

variants = {
    '00-goc': base,
    '01-nghieng-2do': rot(base, 2),
    '02-nghieng-5do': rot(base, 5),
    '03-mo-r1.2': base.filter(ImageFilter.GaussianBlur(1.2)),
    '04-mo-r2.0': base.filter(ImageFilter.GaussianBlur(2.0)),
    '05-jpeg-q30': jpeg(base, 30),
    '06-anh-sang-khong-deu': gradient(base, 0.55),
    '07-bong-do': shadow(base),
    '08-do-phan-giai-50pt': scale(base, 0.5),
    '09-do-phan-giai-35pt': scale(base, 0.35),
    '10-phoi-canh-4pt': skew(base, 0.04),
    '11-nhieu-hat': noise(base, 18),
    '12-chup-dien-thoai': jpeg(noise(gradient(base.filter(ImageFilter.GaussianBlur(0.8)), 0.4), 8), 45).rotate(2.5, resample=Image.BICUBIC, expand=True, fillcolor=235),
    '13-chup-dien-thoai-xau': jpeg(noise(shadow(gradient(scale(skew(base, 0.03, 40), 0.6).filter(ImageFilter.GaussianBlur(1.0)), 0.5)), 12), 35).rotate(-3.5, resample=Image.BICUBIC, expand=True, fillcolor=225),
}
for name, img in variants.items():
    with open(f'{out}/{name}.gray', 'wb') as f:
        f.write(struct.pack('<II', img.width, img.height)); f.write(img.tobytes())
    img.save(f'{out}/{name}.png')
print(len(variants), 'variants')
