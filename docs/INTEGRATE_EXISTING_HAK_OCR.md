# Tích hợp với OCR HAK đã phát triển

## Mã nguồn được kế thừa

1. **HAK Smart OCR AI**: `saoluucvhak-pixel/LUONG_HAK`, nhánh `feature/hak-smart-ocr-ai-windows`, thư mục `apps/hak-smart-ocr-ai/`. Bao gồm Tesseract/Paddle/hybrid, xử lý bảng, Deep Cells, Review Studio, Learning Center, SQLite và xuất dữ liệu.
2. **OCR chấm công Electron**: `saoluucvhak-pixel/LUONG_HAK`, nhánh `feature/hak-smart-ocr-external-engine`, thư mục `LuongHAK_Offline/`, đặc biệt `main/ocr-service.js`, `core/ocr-learning`. Công cụ này là JS/Electron và **chưa được nối trực tiếp qua adapter Python**.

## Cách dùng adapter HAK Smart OCR AI

Chuẩn bị source của nhánh Windows vào một thư mục cục bộ (không chép đè package `hak_ocr` của HAK_OCR_ENGINE). Cài phụ thuộc của app trên máy chạy theo hướng dẫn riêng trong `apps/hak-smart-ocr-ai/README.md`.

```python
from hak_ocr.core import OCRService
from hak_ocr.adapters.smart import SmartOCRAdapter
adapter = SmartOCRAdapter("C:/HAK/SmartOCRAI/apps/hak-smart-ocr-ai")
result = OCRService({"hak-smart": adapter}).process("C:/Documents/bangcong.png", "hak-smart")
print(result.to_dict())
```

- Chạy subprocess qua CLI gốc, tách môi trường và bảo toàn code/lịch sử OCR của app đang có.
- Mỗi lần xử lý dùng kho dữ liệu tạm, tự xóa sau khi hoàn thành.
- Kết quả `tables` ánh xạ về mảng hàng/cột. Chưa ánh xạ các trường review và evidence.
- Không tự ghi kết quả AI vào lương, kế toán hoặc hợp đồng.
- Trường hợp PDF, dịch vụ HAK_OCR_ENGINE rasterize từng trang trước khi chuyển cho adapter; **không sử dụng tối ưu PDF text-native của app gốc**. Đây là việc cần cải tiến sau kiểm thử.
- Không chạy OCR engine thật trong CI; unit test sử dụng fake CLI. Muốn nghiệm thu cần bộ chứng từ mẫu đã ẩn thông tin cá nhân và so sánh chất lượng OCR từng engine.

## Bảo mật

Không đăng ảnh nhân sự, CCCD, số tài khoản hoặc chứng từ thực lên GitHub công khai. Không đưa stdout/stderr của CLI gốc vào log khi thất bại. Xác nhận giấy phép thư viện và model trước khi phát hành Windows.
