# HAK_OCR_ENGINE — 0.2.0

Các mô-đun OCR dùng chung cho ứng dụng offline: xử lý lưới bảng, dựng bảng công, đọc ảnh qua Tesseract, gợi ý chữ số và đối chiếu giấy xác nhận / tăng ca. Đây là thư viện, không phải bộ cài ứng dụng lương.

## Thay đổi mới

- **Thử nghiệm PaddleOCR trong Node** (`js/main/paddle-rec.js`, xem [PADDLE_ONNX.md](PADDLE_ONNX.md)): model nhận dạng PP-OCRv5 xuất ONNX chạy bằng `onnxruntime-node` (phụ thuộc tùy chọn), không cần Python; khớp PaddleOCR Python 244/244 ô. Chưa nối vào `ocr-service`. Kèm bộ ký tự huấn luyện tiếng Việt `js/ocr/paddle/vi_latin_dict.txt` (latin + 90 chữ Việt còn thiếu).
- Bổ sung `table-grid.js` còn thiếu để bộ điều phối đọc bảng nạp được độc lập.
- Biểu mẫu: phân loại giấy vân tay, phiếu tăng ca, danh sách tổng giờ; trường đọc được luôn chờ duyệt.
- Đọc ký hiệu giờ `7h`, `7h00`, `15 giờ 5 phút`, `09:3`; chuẩn hóa thành giờ:phút và giữ chữ gốc.
- Giữ số dòng nguồn: hai lần `7h00` trên hai dòng là hai gợi ý riêng, không gộp mất lần chấm.
- Ngày đủ năm có ISO; thiếu năm được đánh dấu `needsYear`, không tự điền năm. Không tự tính giờ qua đêm hay xác nhận chữ ký.
- Gói tích hợp có manifest SHA256 và kiểm tra nạp độc lập trong CI.

## Dùng với Node.js

Yêu cầu Node.js >=22. Các hàm phân tích chữ/lưới không cần Tesseract:

```js
const OCR = require('./HAK_OCR_ENGINE');
const review = OCR.documentReview('GIẤY XÁC NHẬN VÂN TAY\n7h ngày 6/7');
// kind: FINGERPRINT_EXCEPTION
// candidates: time/date + sourceLine, status PENDING_REVIEW
// requiresReview: true; canAutoImport: false
```

`index.js` xuất `documentReview`, `parseTable`, `analyze`, `grid`, `createOcrService`, `sanitizeOcrItems` và `version`. API cũ trong `js/core/timesheet-parse.js` vẫn giữ nguyên; metadata mới chỉ bổ sung.

## Đọc ảnh offline

Host cần cài `tesseract.js@5.1.1` cùng runtime tương thích, cung cấp `ocr/worker.js` và dữ liệu ngôn ngữ offline `vie`/`eng` trong `ocr/lang` dưới `appDir`. Có thể dùng bộ tài nguyên đã được triển khai của HAK_LUONG_OFFLINE. Gói này có mô hình chữ số và NOTICE, **không chứa tessdata/worker đầy đủ**; cần chuẩn bị các tài nguyên trên trước khi chạy offline. Không coi gói thư viện là bản OCR ảnh chạy ngay không cần tài nguyên host.

```js
const service = OCR.createOcrService({ appDir: '/absolute/path/to/host', tesseract: require('tesseract.js') });
const result = await OCR.analyze({g: grayPixels, w: width, h: height}, {
  ocr: items => service.batch(OCR.sanitizeOcrItems(items))
}, { onProgress: text => console.log(text) });
await service.terminate();
```

Ảnh là mảng xám Uint8Array, không phải đường dẫn. Host tự giới hạn đầu vào, xác thực người dùng và bảo vệ dữ liệu. `result.table` là bảng xem trước; khi không dựng được bảng, `result.documentReview` chứa nhánh biểu mẫu. Luồng biểu mẫu chỉ tạo gợi ý, không tạo dòng công hay ghi dữ liệu.

Với trình duyệt, nạp `js/core/table-grid.js`, `js/core/timesheet-parse.js`, `js/core/timesheet-ocr.js` theo thứ tự; API ở `HAKCore.grid`, `HAKCore.tsparse`, `HAKCore.tsocr`. Host cung cấp hàm OCR offline. Không nạp mô-đun `main` bằng thẻ script.

## Kiểm tra và lấy gói

```text
npm test
npm run build
```

Gói nằm trong `dist/HAK_OCR_ENGINE`; `manifest.json` liệt kê phiên bản, các tệp và SHA256. GitHub Actions trên nhánh `feature/document-review-v2` kiểm thử và tải gói lên Artifacts. Tệp `HAK_OCR_ENGINE.zip` cũ ở gốc là bản lưu lịch sử, không đại diện phiên bản mới; dùng artifact theo commit đã kiểm tra.

## Giới hạn nghiệm thu

Bản trước phân loại đúng 5 biểu mẫu mục tiêu trong bộ ảnh riêng tư, nhưng phần lớn trường chữ tay chưa đọc được. Việc hỗ trợ thêm cách viết giờ trong **chữ OCR đầu vào** không chứng minh mô hình đã đọc đúng nét bút trên ảnh. Bản này không thay trọng số mô hình MNIST, không tuyên bố nghiệm thu chữ tay tiếng Việt. Chỉ dữ liệu giả lập và số liệu tổng hợp được đưa vào repo; không đưa hồ sơ lương thật vào mã nguồn.

Chi tiết API biểu mẫu: [DOCUMENT_REVIEW.md](DOCUMENT_REVIEW.md). Mô hình chữ số và nguồn: [HANDWRITTEN_DIGITS.md](HANDWRITTEN_DIGITS.md).
