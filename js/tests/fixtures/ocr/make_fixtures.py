# Sinh ảnh / PDF MẪU GIẢ LẬP cho kiểm thử OCR chấm công (tên giả, số liệu giả — không dùng dữ liệu thật).
# Chạy: python3 tests/fixtures/ocr/make_fixtures.py   (cần Pillow + font DejaVu)
import os, random
from PIL import Image, ImageDraw, ImageFont
OUT = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f = ImageFont.truetype(FONT, 22); fb = ImageFont.truetype(BOLD, 30); fs = ImageFont.truetype(FONT, 20)

# 1) Bảng chấm công in: người × ngày (tháng 09/2026, 30 ngày), cột Tổng công
PEOPLE = [("E2E Nhân Viên", [1] * 26 + [0.5, 1, 1, 0]), ("Phạm Minh Khoa", [1, 1, 0] * 10), ("Đỗ Thu Hằng", [1] * 15 + [0] * 15)]
def table_img():
    days = 30; x0, y0 = 40, 160; nameW, dayW, totW, rowH = 300, 46, 110, 60
    W = x0 * 2 + nameW + days * dayW + totW; H = y0 + rowH * (len(PEOPLE) + 1) + 120
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((W // 2 - 300, 40), "BẢNG CHẤM CÔNG THÁNG 09/2026", font=fb, fill=0)
    cols = [x0, x0 + nameW] + [x0 + nameW + dayW * (i + 1) for i in range(days)] + [x0 + nameW + days * dayW + totW]
    rows = [y0 + rowH * i for i in range(len(PEOPLE) + 2)]
    for x in cols: d.line([(x, rows[0]), (x, rows[-1])], fill=0, width=2)
    for y in rows: d.line([(cols[0], y), (cols[-1], y)], fill=0, width=2)
    def put(c, r, t, font=f):
        bx = d.textbbox((0, 0), t, font=font); tw, th = bx[2] - bx[0], bx[3] - bx[1]
        d.text(((cols[c] + cols[c + 1] - tw) / 2, (rows[r] + rows[r + 1] - th) / 2 - bx[1]), t, font=font, fill=0)
    put(0, 0, "Họ và tên")
    for i in range(days): put(i + 1, 0, str(i + 1), fs)
    put(days + 1, 0, "Tổng công", fs)
    for r, (name, vals) in enumerate(PEOPLE):
        d.text((cols[0] + 10, rows[r + 1] + 16), name, font=f, fill=0)
        for i, v in enumerate(vals):
            if v: put(i + 1, r + 1, "0.5" if v == 0.5 else "1", fs)
        put(days + 1, r + 1, ("%g" % sum(vals)), fs)
    return im

# 2) Lịch làm dọc (ngày theo hàng), cột Công / Cơm viết tay mô phỏng bằng nét "1" đứng
def vertical_img():
    random.seed(7); days = 30; x0, y0 = 60, 150; cw = [130, 150, 150]; rowH = 44
    W = x0 * 2 + sum(cw); H = y0 + rowH * (days + 2) + 60
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((x0, 30), "Lịch làm Võ Văn Tâm", font=fb, fill=0); d.text((x0, 80), "Tháng 09/2026", font=f, fill=0)
    xs = [x0, x0 + cw[0], x0 + cw[0] + cw[1], x0 + sum(cw)]; ys = [y0 + rowH * i for i in range(days + 3)]
    for x in xs: d.line([(x, ys[0]), (x, ys[-1])], fill=0, width=2)
    for y in ys: d.line([(xs[0], y), (xs[-1], y)], fill=0, width=2)
    def put(c, r, t):
        bx = d.textbbox((0, 0), t, font=f); d.text(((xs[c] + xs[c + 1] - (bx[2] - bx[0])) / 2, (ys[r] + ys[r + 1] - (bx[3] - bx[1])) / 2 - bx[1]), t, font=f, fill=0)
    put(0, 0, "Ngày"); put(1, 0, "Công"); put(2, 0, "Cơm")
    com = [1] * days; com[9] = 0; com[20] = 0
    for i in range(days):
        put(0, i + 1, str(i + 1))
        for c, on in ((1, 1), (2, com[i])):
            if on:
                cx = (xs[c] + xs[c + 1]) / 2 + random.randint(-6, 6); top = ys[i + 1] + 8; bot = ys[i + 2] - 8
                d.line([(cx + random.randint(-3, 3), top), (cx, bot)], fill=0, width=4)
    put(0, days + 1, "TC"); put(1, days + 1, str(days)); put(2, days + 1, str(sum(com)))
    return im

# 3) Bảng chấm công TAY của tổ (α22): ngày theo hàng, MỖI NGƯỜI 1 CỘT, 2 khối ngày 1–15 | 16–30 đặt cạnh nhau.
#    Ô đánh dấu x (x = 1 công, xx = 2, xxx = 3), 1 ô ghi giờ "7h-15h" (= 8 giờ = 1 công). Tên giả.
MARK_PEOPLE = ["Lê Văn An", "Trần Bình", "Ngô Cường"]
def mark_values():
    random.seed(11); v = {}
    for p in range(3):
        for dd in range(1, 31): v[(p, dd)] = [0, 1, 1, 2, 3][random.randint(0, 4)] if dd % 7 else 0
    return v
def draw_x(d, cx, cy, s, rnd):
    j = lambda: rnd.randint(-2, 2)
    d.line([(cx - s + j(), cy - s + j()), (cx + s + j(), cy + s + j())], fill=0, width=3)
    d.line([(cx + s + j(), cy - s + j()), (cx - s + j(), cy + s + j())], fill=0, width=3)
def marks_img():
    vals = mark_values(); rnd = random.Random(5)
    x0, y0, dayW, colW, rowH, gap = 40, 150, 70, 150, 46, 40
    panelW = dayW + colW * 3; W = x0 * 2 + panelW * 2 + gap; H = y0 + rowH * 17 + 60
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((x0, 40), "BẢNG CHẤM CÔNG TỔ BỐC XẾP THÁNG 09/2026", font=fb, fill=0)
    for k, (d0, d1) in enumerate(((1, 15), (16, 30))):
        px = x0 + k * (panelW + gap); xs = [px, px + dayW] + [px + dayW + colW * (i + 1) for i in range(3)]
        ys = [y0 + rowH * i for i in range(d1 - d0 + 4)]
        for x in xs: d.line([(x, ys[0]), (x, ys[-1])], fill=0, width=2)
        for y in ys: d.line([(xs[0], y), (xs[-1], y)], fill=0, width=2)
        def put(c, r, t, font=fs):
            bx = d.textbbox((0, 0), t, font=font); d.text(((xs[c] + xs[c + 1] - (bx[2] - bx[0])) / 2, (ys[r] + ys[r + 1] - (bx[3] - bx[1])) / 2 - bx[1]), t, font=font, fill=0)
        put(0, 0, "Ngày")
        for i, nm in enumerate(MARK_PEOPLE): put(i + 1, 0, nm)
        for r, dd in enumerate(range(d0, d1 + 1)):
            put(0, r + 1, str(dd))
            for p in range(3):
                n = vals[(p, dd)]
                if p == 1 and dd == 9: put(p + 1, r + 1, "7h-15h"); continue
                cy = (ys[r + 1] + ys[r + 2]) / 2; cx0 = (xs[p + 1] + xs[p + 2]) / 2 - (n - 1) * 17
                for m in range(n): draw_x(d, cx0 + m * 34 + rnd.randint(-2, 2), cy + rnd.randint(-2, 2), 11, rnd)
        put(0, d1 - d0 + 2, "TC")
    return im

# 4) Lịch làm theo ca (α22): ngày theo hàng, mỗi người 1 cột; ô ghi số ca "1", "2", "3", "1+2"; "X" = nghỉ. Tên giả.
CA_PEOPLE = ["Phan Thị Dung", "Hồ Văn Em"]
CA_VALS = [["1", "2", "3", "1+2", "X", "1", "", "2", "1+2", "3", "1", "X", "2", "1", "2"], ["2", "X", "1", "1", "1+2", "", "3", "1", "2", "X", "1+2", "1", "3", "2", "1"]]
def shifts_img():
    x0, y0, dayW, colW, rowH = 40, 150, 80, 220, 46; days = len(CA_VALS[0])
    xs = [x0, x0 + dayW, x0 + dayW + colW, x0 + dayW + colW * 2]; ys = [y0 + rowH * i for i in range(days + 2)]
    W = xs[-1] + x0; H = ys[-1] + 60
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((x0, 40), "LỊCH LÀM THEO CA THÁNG 10/2026", font=fb, fill=0)
    for x in xs: d.line([(x, ys[0]), (x, ys[-1])], fill=0, width=2)
    for y in ys: d.line([(xs[0], y), (xs[-1], y)], fill=0, width=2)
    def put(c, r, t, font=f):
        bx = d.textbbox((0, 0), t, font=font); d.text(((xs[c] + xs[c + 1] - (bx[2] - bx[0])) / 2, (ys[r] + ys[r + 1] - (bx[3] - bx[1])) / 2 - bx[1]), t, font=font, fill=0)
    put(0, 0, "Ngày")
    for i, nm in enumerate(CA_PEOPLE): put(i + 1, 0, nm, fs)
    for r in range(days):
        put(0, r + 1, str(r + 1))
        for p in range(2):
            if CA_VALS[p][r]: put(p + 1, r + 1, CA_VALS[p][r])
    return im

a = table_img(); a.save(os.path.join(OUT, "bang-cham-cong-mau.png"), optimize=True)
b = vertical_img(); b.save(os.path.join(OUT, "lich-lam-doc-mau.png"), optimize=True)
a.convert("RGB").save(os.path.join(OUT, "bang-cham-cong-mau.pdf"), "PDF", resolution=150)
# bang-cham-cong-mau-pdfjs.png = trang PDF trên do app vẽ bằng pdf.js (lấy từ canvas trong app, chuyển xám) — dùng cho I-OCR-04
c = marks_img(); c.save(os.path.join(OUT, "cham-cong-tay-x-mau.png"), optimize=True)
e = shifts_img(); e.save(os.path.join(OUT, "lich-ca-mau.png"), optimize=True)
print("ok", a.size, b.size, c.size, e.size)
if os.environ.get("EXPECT"):  # in giá trị mong đợi của bảng dấu x để đối chiếu với test
    v = mark_values(); v[(1, 9)] = 1
    for p in range(3): print(MARK_PEOPLE[p], [v[(p, dd)] for dd in range(1, 31)], sum(v[(p, dd)] for dd in range(1, 31)))
