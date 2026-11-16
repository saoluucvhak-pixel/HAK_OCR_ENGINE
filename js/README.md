# HAK OCR — bản JavaScript (Node / Electron)

Bộ OCR chạy **bên trong app Electron** của HAK, chuyển nguyên trạng từ `LuongHAK_Offline`
(LUONG_HAK, nhánh `audit/luong-hak-offline-v10-3-quality`, commit `59fa2f5`).

| Thư mục | Nội dung |
|---|---|
| `core/table-grid.js` | Tìm lưới bảng (đường kẻ ngang/dọc, chỉnh nghiêng, ô gộp tiêu đề) trên ảnh xám — JS thuần, chạy cả renderer lẫn Node |
| `core/timesheet-parse.js` | Dựng bảng chấm công / chấm cơm từ các ô đã đọc |
| `core/timesheet-ocr.js` | Điều phối: đoán chiều ảnh (4 hướng) → tìm ô → cắt ô → OCR theo lô → bảng xem trước. Nét "1" viết tay mảnh không đọc ra → coi là "1" và đánh dấu cần kiểm tra |
| `core/ocr-learning/` | **Học từ chỗ người dùng sửa**: mỗi ô bị sửa tự ghi một mẫu; nhớ tên nhân viên; thư viện bố cục; quy tắc; đọc lớp chữ của PDF |
| `main/ocr-service.js` | Tesseract.js 5.1.1 ở tiến trình chính, **không tải gì từ mạng** |
| `main/ocr-library.js` | Lưu thư viện mẫu đã học xuống đĩa |
| `ocr/lang/` | Gói ngôn ngữ **vie** và **eng** đóng kèm (tessdata_best_int, Apache-2.0) — xem `ocr/README.md` |
| `ocr/worker.js` | Bọc worker của tesseract.js để chạy được trong Electron mà không cố tải qua mạng |

## Dùng

```bash
cd js && npm install && npm test     # 60 test, gồm OCR thật trên ảnh mẫu bảng chấm công
```
```js
const ocr = require("@hak/ocr-js");             // hoặc require("<repo>/js")
const svc = ocr.createOcrService({ appDir: __dirname + "/node_modules/@hak/ocr-js" });
```
Trong Electron: đặt `ocr/` ngoài asar (`build.asarUnpack: ["**/ocr/**"]`) vì worker_threads không chạy được file trong asar.

## So với bản Python ở gốc repo

| | JS (`js/`) | Python (gốc repo) |
|---|---|---|
| Dùng trong | App Electron (lương, kho…) | Ứng dụng OCR độc lập trên Windows, dòng lệnh |
| Bảng chấm công | Lưới bảng + học từ chỗ sửa, nhớ tên | OpenCV + OCR sâu từng ô, Review Studio |
| Gói tiếng Việt | Đóng kèm trong `js/ocr/lang` | Cài Tesseract + vie, hoặc đóng gói vào `vendor/tesseract` |
| Đọc Word/Excel/PPT | — | `cli.py office` (MarkItDown) |

Cả hai đều chỉ đưa ra **gợi ý**; dữ liệu phải qua bảng xem trước / người duyệt trước khi tính lương hay thanh toán.

## Không chuyển sang đây

3 kiểm thử gắn với chức năng riêng của app lương (Full Backup chứa thư viện OCR, kho chứng từ, liên kết ô chấm công) vẫn ở `LuongHAK_Offline/tests` — đã đánh dấu tại chỗ trong file test.
