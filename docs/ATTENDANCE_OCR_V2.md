# HAK OCR CENTER — bảng chấm công V2

Triển khai thử nghiệm không đưa ảnh nhân sự lên repo công khai.

## Quy trình
1. Xoay, hiệu chỉnh góc chụp và phối cảnh **ngoại tuyến**; lưu bản gốc bất biến.
2. Thử phát hiện đường kẻ qua `hak_ocr.grid_detection.detect_grid` (OpenCV tùy chọn), sau đó người vận hành xác nhận tọa độ, số cột/ngày trên giao diện.
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

## Pipeline thử nghiệm

`run_attendance_pilot(image, engine, xs, ys, first_data_row=..., first_day_col=..., days=30, total_col=...)` gọi OCR cho từng ô sau khi xác nhận lưới và tạo báo cáo `NEEDS_REVIEW`. Không tự duyệt kết quả hoặc xuất lương.

## Giới hạn hiện tại
- Có detector OpenCV tùy chọn để **đề xuất** tọa độ đường kẻ; kết quả có thể không chính xác trên ảnh cong, nhiễu, bàn lệch và vẫn cần kiểm tra thủ công.
- Chưa thực hiện OCR nhận dạng từng ô end-to-end với ảnh thật của người dùng.
- Bảng có ô gộp/không kẻ, mờ, nghiêng nhiều cần thuật toán nhận dạng cấu trúc riêng.
- `read_sum` chỉ tổng ô số đọc được; ô trống không phải 0. Tổng khớp không đồng nghĩa đã duyệt.
- Chứng từ chấm công chứa dữ liệu cá nhân phải lưu trong máy hoặc kho riêng có phân quyền.
