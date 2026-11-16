# HAK Smart OCR AI 1.2.0-alpha — Windows EXE Build Kit

## Trạng thái quan trọng

Đây là **gói mã nguồn và công cụ đóng gói EXE**. Gói hiện tại **không chứa bản Windows EXE đã biên dịch**. Môi trường phát triển ban đầu là Linux; chưa có bằng chứng ứng dụng chạy thành công trên Windows 10/11 thật. Không nên đặt tên ZIP này là bộ cài đã nghiệm thu.

**Bản EXE sẽ xuất ra khi build trên Windows:**

- `dist/HAKSmartOCRAI/HAKSmartOCRAI.exe`: ứng dụng Desktop và toàn bộ thư viện trong cùng một thư mục. Không được tách file EXE ra khỏi thư mục đó.
- `dist/HAKSmartOCRAI-Portable-1.2.0-alpha-Windows-x64.zip`: bản portable có EXE + thư viện + Tesseract tiếng Việt/Anh.
- `dist/HAKSmartOCRAI-Setup-1.2.0-alpha.exe`: bộ cài Inno Setup, mở ứng dụng từ Start Menu/Desktop.

Sau khi cài, dữ liệu vẫn ở `%LOCALAPPDATA%\HAK\SmartOCRAI\`. Gỡ ứng dụng **không tự xóa dữ liệu**.

## Cách 1: Bấm BUILD_EXE_WINDOWS.cmd trên máy Windows để tự build

Trên **máy BUILD Windows 10/11 x64** (có thể có Internet để cài công cụ; ứng dụng của người dùng sau này vẫn offline), chuẩn bị:

1. **Python 3.11 x64**, có Python Launcher `py.exe`.
2. **Tesseract OCR 5 x64** đã cài đặt với hai ngôn ngữ `vie` và `eng`.
3. **Inno Setup 6**, để tạo bộ cài `.exe` (nếu chỉ muốn portable có thể dùng `-PortableOnly`).
4. Phần mềm không chứa ảnh nhân sự mẫu hay thông tin lương riêng của khách hàng.

Giải nén nguồn, nhấp đúp `BUILD_EXE_WINDOWS.cmd`. Chờ script tự cài dependencies (trên máy BUILD), chạy tests, kiểm tra Tesseract, build bằng PyInstaller, khởi chạy EXE vừa đóng gói với cờ `--self-test` và biên dịch Setup qua Inno Setup.

**Lỗi sẽ dừng quá trình build**, không cho xuất setup giả hoàn thành.

Để build offline cả trên máy build: trước đó tải đủ wheels Windows vào `wheelhouse` bằng một máy chuẩn bị, sau đó chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1 -OfflineBuild
```

## Cách 2: Build bằng GitHub Actions (Windows runner)

1. Tạo repository **private** mới, không đưa chứng từ thực hay ảnh nhân sự vào repository.
2. Đưa toàn bộ thư mục source vào repo (bao gồm `.github/workflows/build-windows-exe.yml`).
3. Trên GitHub mở **Actions → Build Windows EXE - HAK Smart OCR AI → Run workflow**.
4. Khi workflow thành công, mở run → **Artifacts** và tải `HAKSmartOCRAI-Windows-x64-1.2.0-alpha`.
5. Giải nén artifact để lấy **Setup EXE**, Portable ZIP và bản kiểm tra đóng gói.

GitHub Actions có Internet **chỉ trong lúc build**, để cài công cụ và tải `vie/eng.traineddata` từ dự án Tesseract; phần mềm chạy sau build không tải hoặc gọi API mạng.

**Lưu ý:** workflow này đã được chuẩn bị nhưng **chưa được chạy thành công và chưa thể khẳng định các gói Chocolatey/Windows luôn tương thích**. Nếu Chocolatey cài vào thư mục khác, cần chỉnh đường dẫn Tesseract cho phù hợp. Việc sử dụng GitHub cũng có giới hạn thời gian/tài nguyên phụ thuộc tài khoản.

## Nội dung được đóng gói

**Core (mặc định, build được nếu đủ dependencies):**

- Python runtime và giao diện PySide6.
- Đọc PDF native/scan và OCR tiếng Việt/Anh với Tesseract.
- Xử lý bảng chấm công, đánh dấu ô gợi ý, sửa và duyệt, SQLite, Learning Engine dạng quy tắc, Excel/JSON/CSV, sao lưu.
- Tesseract 5 + `vie.traineddata`, `eng.traineddata` được sao chép từ máy build vào thư mục EXE.

**Advanced — chỉ khi có model thực sự:**

- PaddleOCR, Docling, TrOCR, UVDoc và GGUF **không được giả vờ là có trong gói mặc định**.
- Thư mục `vendor/models/` hiện **không có trọng số model**. Chỉ bật `-Advanced` khi đã cung cấp đầy đủ các trọng số tương thích, wheel Windows và kiểm thử bằng dữ liệu thật.
- Không cam kết hỗ trợ chữ viết tay tiếng Việt nếu checkpoint chưa được đánh giá tương ứng.

## Chạy kiểm tra sau khi build

```powershell
.\dist\HAKSmartOCRAI\HAKSmartOCRAI.exe --self-test .\validation\local-exe-check.json --require-bundled
Get-Content .\validation\local-exe-check.json
```

Phải kiểm tra `ok=true`, `frozen=true`, `tesseract_vie=true`, `tesseract_eng=true`, `qt_import=true`, `sqlite_writable=true`. Đây mới là kiểm tra vận hành thành phần; vẫn phải **khởi động giao diện bằng chuột và kiểm thử 10 ảnh thực tế trên máy Windows sạch không có Internet**.

## Yêu cầu nghiệm thu trước khi sử dụng thực tế

- Cài từ file Setup trên Windows 10 và Windows 11 x64 sạch, không cài Python/Tesseract từ trước và ngắt Internet.
- Chạy được UI, nhập ảnh, nhập PDF native/scan, đọc tiếng Việt, sửa từng ô, xuất Excel, sao lưu, thoát và mở lại không mất dữ liệu.
- Kiểm tra file EXE/ZIP bằng SHA-256 và quét bảo mật.
- Kiểm tra giấy phép PyMuPDF, Tesseract, model và các thư viện đi kèm trước khi phân phối thương mại.
- Dữ liệu công/lương/tài khoản **chỉ sử dụng sau khi được người có thẩm quyền duyệt**.

## Một số lỗi thường gặp

| Hiện tượng | Nguyên nhân / khắc phục |
|---|---|
| `py -3.11` không chạy | Chưa cài đúng Python 3.11 x64 + Python Launcher trên máy build |
| Không tìm thấy `vie.traineddata` | Bổ sung ngôn ngữ tiếng Việt cho Tesseract trên máy build |
| PyInstaller build thành công nhưng EXE self-test không đạt | Thư viện native hoặc tessdata chưa được gom đủ; xem `validation/packaged-check.json` |
| Thiếu Inno Setup | Cài Inno Setup 6 hoặc chạy `-PortableOnly` |
| Paddle/Docling unavailable | Đây là bản Core; muốn AI nâng cao cần các model offline tương thích và build Advanced |
