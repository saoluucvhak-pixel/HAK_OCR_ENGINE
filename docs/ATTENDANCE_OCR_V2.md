# HAK OCR CENTER — bảng chấm công V2

Triển khai thử nghiệm không đưa ảnh nhân sự lên repo công khai.

## Quy trình
1. Xoay, hiệu chỉnh góc chụp và phối cảnh **ngoại tuyến**; lưu bản gốc bất biến.
2. Phát hiện đường kẻ và tọa độ lưới, xác nhận số cột/ngày trên giao diện.
3. `extract_cells(image, xs, ys)` tách từng ô với tọa độ ảnh gốc; `save_crops(...)` hỗ trợ xử lý theo lô.
4. OCR riêng từng ô bằng PaddleOCR hoặc HAK Smart OCR AI, có thể so sánh kết quả Unlimited-OCR.
5. Ánh xạ từng ngày thành `{raw,bbox,confidence}`. Dùng `audit_attendance` để kiểm tra ô trống, ký tự bất thường, mức tin cậy, số ngày, sai lệch tổng.
6. Review Studio kiểm duyệt từng ô dựa trên ảnh gốc. Không tự ghi vào LUONG_HAK.

## API

```python
from hak_ocr.table_grid import extract_cells, save_crops
from hak_ocr.attendance import audit_attendance
cells = extract_cells("sample.png", xs=[0,30,60], ys=[0,25,50])
metadata = save_crops(cells, "./local-private-crops")
report = audit_attendance([{"employee_id":"test","days":[{"raw":"1","confidence":0.99}]*30,"total":{"raw":"30"}}])
assert report["payroll_ready"] is False
```

## Giới hạn hiện tại
- Tọa độ đường kẻ `xs, ys` hiện cần được cung cấp từ người vận hành hoặc detector bên ngoài; **chưa tự phát hiện lưới**.
- Chưa thực hiện OCR nhận dạng từng ô end-to-end với ảnh thật của người dùng.
- Bảng có ô gộp/không kẻ, mờ, nghiêng nhiều cần thuật toán nhận dạng cấu trúc riêng.
- `read_sum` chỉ tổng ô số đọc được; ô trống không phải 0. Tổng khớp không đồng nghĩa đã duyệt.
- Chứng từ chấm công chứa dữ liệu cá nhân phải lưu trong máy hoặc kho riêng có phân quyền.
