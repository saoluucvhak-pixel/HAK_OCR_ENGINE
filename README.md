# HAK OCR ENGINE

Thư viện OCR **offline-first**, mã nguồn mở nội bộ cho các ứng dụng HAK (Lương, Kho, HDMB, Hồ sơ vay). Phiên bản 0.1.0 là **developer preview**, chưa nghiệm thu độ chính xác thực tế.

## Cấu trúc

- `hak_ocr/core.py`: API OCR, kết quả JSON theo từng trang, hash tài liệu, giới hạn kích thước và số trang.
- `hak_ocr/adapters/paddle.py`: adapter PaddleOCR 3.x, phụ thuộc tùy chọn.
- `hak_ocr/adapters/unlimited.py`: adapter Baidu Unlimited-OCR qua SGLang OpenAI-compatible API chạy tại `127.0.0.1`. Không tự tải model, không kết nối máy chủ Internet.
- `hak_ocr/pdf.py`: chuyển PDF sang ảnh tạm; xóa ảnh trung gian sau xử lý.
- `hak_ocr/cli.py`: CLI tùy chọn engine.
- `tests/`: unit tests không cần GPU hoặc chứng từ thật.

## Cài đặt phát triển

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m hak_ocr.cli /path/to/document.png --engine paddle --out result.json
python -m hak_ocr.cli /path/to/document.pdf --engine unlimited --endpoint http://127.0.0.1:10000 --out result.json
```

Engine thực tế yêu cầu cài phụ thuộc phù hợp: `paddleocr` (PaddleOCR), `PyMuPDF` (PDF), hoặc một SGLang local server đang chạy model Unlimited-OCR trên GPU NVIDIA tương thích. **Offline thực sự** yêu cầu chuẩn bị sẵn trọng số model và phụ thuộc; adapter không bảo đảm PaddleOCR sẽ không tải tài nguyên nếu chưa cấu hình model cục bộ.

## Bảo mật và giới hạn

Mặc định không gửi chứng từ ra Internet. Adapter Unlimited chỉ chấp nhận URL HTTP có địa chỉ loopback IP tường minh, không theo proxy. Không nên cho phép máy khác truy cập local service nếu chưa thiết lập xác thực. Không commit chứng từ thật hoặc thông tin nhạy cảm.

Bộ mã nguồn Unlimited-OCR do Baidu công bố theo MIT; **giấy phép model weights phải kiểm tra độc lập** trước khi phân phối thương mại. HAK không sao chép mã nguồn/weights của Baidu vào repository này.

Mô-đun PaddleOCR đọc văn bản cơ bản; các tính năng bảng biểu, chữ viết tay tiếng Việt, benchmark, đóng gói Windows EXE, và xác minh nghiệp vụ chưa nghiệm thu.

Nguồn tham khảo: https://github.com/baidu/Unlimited-OCR

Xem [Roadmap](docs/ROADMAP.md).
