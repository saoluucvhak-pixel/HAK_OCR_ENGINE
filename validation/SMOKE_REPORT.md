# Báo cáo thử nghiệm bản nguồn HAK Smart OCR AI 1.0-dev

**Môi trường được sử dụng:** Linux container, Python 3.13, Tesseract 5 với `vie+eng`, OpenCV, PyMuPDF, Pillow, SQLite, pytest.

## Tự động

- 14/14 unit/integration tests qua: kiểm tra file trùng, SHA256, correction history, rule holdout, rollback, bảo vệ verified, bảng grid, xuất CSV/XLSX/JSON, backup SQLite/ZIP và restore, template, parse số công, PDF native, từ chối duyệt tài liệu chưa OCR.
- Nguồn Python vượt `compileall`.

## Thử nghiệm có sử dụng ảnh chứng từ người dùng đã cung cấp (không đóng gói ảnh vào ZIP)

| Nhóm ảnh | Kết quả máy đọc được | Hạn chế quan sát |
|---|---|---|
| Ảnh lịch công 30 ngày, 3 cột | Phân loại bảng công, phát hiện lưới 3 cột (37 hàng máy tạo) | Lưới thừa so với mẫu; OCR nhiều chữ số nhỏ bị bỏ sót, kể cả khi bật OCR từng ô |
| Ảnh bảng công xuất hàng HAK, chụp ngang | Phân loại bảng công, tìm được vùng bảng | OCR thiếu/nhầm một số ô và số tổng |
| Ảnh bảng xác nhận công tác chụp nghiêng | Tự xoay 90 độ, phát hiện vùng có bảng | Tiêu đề/nhân sự/chữ nhỏ OCR sai; cần sửa tay và điều chỉnh mẫu |
| Ảnh chụp một hàng nghiệp vụ phần mềm | Nhận được một phần thông tin dạng bảng | Lỗi ký tự, ngày và số tiền. Không an toàn để dùng trực tiếp vào thanh toán |

Không sử dụng tên nhân viên, CCCD, thông tin tài khoản hay nội dung ảnh gốc trong gói phân phối mã nguồn.

## Chưa nghiệm thu

- **Chưa chạy GUI PySide6 thực tế** trong môi trường này vì môi trường không cài PySide6; chỉ kiểm tra cú pháp nguồn.
- **Chưa build/cài/chạy Windows EXE**, chưa có máy Windows offline sạch để chứng minh runtime không thiếu DLL/model.
- **Chưa đạt chỉ tiêu chính xác** OCR ô bảng chấm công trên ảnh thật; bản này là nền tảng thử nghiệm, không phải sản phẩm áp dụng tính lương tự động.
- Chưa huấn luyện weights mô hình và chưa đo CER/WER/field-accuracy trên bộ ground-truth chuẩn.

## Tiêu chí bắt buộc cho giai đoạn tiếp theo

Phát triển thêm nhận dạng bảng sâu, phát hiện phối cảnh, OCR riêng ô số, xử lý dòng gộp, phân loại tài liệu từ tin nhắn. Thu thập 50-100 chứng từ có gắn nhãn do người dùng duyệt, dành riêng tập kiểm tra để đo tiến bộ. Kiểm thử build Windows x64 trên máy mất Internet với model/dll được đóng gói hoàn chỉnh trước khi phát hành bản dùng thực tế.

## Thử nghiệm nâng cấp MVP 1.0.1 (2026-10-16)

- `pytest -q`: **16/16 PASS** trong môi trường Linux.
- Đã kiểm thử tính phân biệt `blank` với `0` và chuỗi OCR bất hợp lệ; sheet `Doi_chieu_cong` không coi tổng các ô có số là bảng công cuối cùng.
- Chưa chạy đo lại CER/WER trên 10 ảnh gốc; không khẳng định tăng độ chính xác nhận dạng so với MVP trước.
- Chưa chạy bản GUI PySide6 hoặc kiểm thử EXE Windows sạch.


## Nâng cấp MVP 1.0.2 — 16/10/2026

- `pytest -q`: **23/23 PASS**; kiểm thử bổ sung gồm chữ số 1 dạng nét mảnh, dữ liệu trống, khôi phục tiêu đề OCR hai lần, chữ ký hình học bảng, chống duyệt nhầm bảng cũ sau khi chạy lại OCR, xuất Excel ô gợi ý.
- Benchmark với ảnh lịch công dọc 30 ngày người dùng đã gửi: dự đoán khớp **60/60 ô công/cơm** trong tập nhãn tham khảo thủ công và khôi phục nhãn `CƠM`. Benchmark `scripts/benchmark_table.py` tái lập được; không đưa ảnh gốc vào ZIP nguồn.
- Bảng có 32 hàng bao gồm header và hàng cuối; nhãn ngày OCR có lỗi, được đánh dấu ngày suy luận và không cho xác nhận toàn bộ cho đến khi sửa/đối chiếu.
- Đây là kết quả trên **một ảnh và một bộ nhãn tham khảo chưa được phê duyệt**, không thể suy ra độ chính xác của 9 ảnh còn lại, ảnh viết tay, máy khác hoặc tài liệu khác.
- Chưa test GUI PySide6 thực tế trên Windows, chưa build EXE/installer Windows.
