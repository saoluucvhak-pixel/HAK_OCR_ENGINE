# Ảnh kiểm thử nắn thẳng trang

`00-goc.png` là ảnh bảng chấm công **giả lập** (tên người và số công bịa, sinh bằng `tests/fixtures/ocr/make_fixtures.py` của HAK_LUONG_OFFLINE). Các ảnh còn lại được làm xấu từ ảnh đó bằng `make-degraded.py` (Pillow + numpy): xoay 2° / 5°, phối cảnh kiểu camera 4%, giả lập chụp điện thoại (mờ, nhiễu, ánh sáng không đều, nén JPEG, nghiêng 2,5°) và bản chụp xấu hơn (thêm bóng đổ, độ phân giải 60%, nghiêng −3,5°).

Không chứa ảnh hay dữ liệu nhân viên thật. Đây là ảnh tổng hợp: chứng minh đường xử lý hình học, **không** thay cho nghiệm thu trên ảnh chụp thật.

Tạo lại: `python make-degraded.py <đường dẫn bang-cham-cong-mau.png> <thư mục ra>`.
