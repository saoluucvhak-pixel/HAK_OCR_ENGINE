# API đối chiếu biểu mẫu v2

`documentReview(text)` nhận chuỗi OCR (giới hạn 100.000 ký tự), không đọc tệp hoặc gửi mạng, không ghi dữ liệu.

Kết quả `kind`: `FINGERPRINT_EXCEPTION`, `OVERTIME_SLIP`, `OVERTIME_SUMMARY`, hoặc `UNKNOWN`. Đây là phân loại dựa trên tiêu đề chữ OCR, không có xác suất mô hình.

Mỗi candidate có `field` (`date`, `time`, `name`), `value`, `source` (dòng OCR), `sourceLine` (bắt đầu từ 1), `status: PENDING_REVIEW`. Ngày có `normalized` (ISO nếu đủ năm) và `needsYear`; giờ có `raw`, `minutesExplicit`. `7h` được diễn giải là 07:00 và `minutesExplicit=false`; vẫn phải đối chiếu vì OCR có thể làm mất phút. Năm hợp lệ 1900–2099. Ngày 29/2 chưa có năm vẫn cần điền năm và kiểm tra lại, không được coi đã hợp lệ cho năm hiện tại.

Gợi ý lặp cùng trường/giá trị trên cùng dòng được gộp; cùng giá trị trên hai dòng khác nhau được giữ. Chưa có liên kết chắc chắn giữa họ tên/ngày/giờ và hàng nghiệp vụ: không tự ghép các gợi ý thành một lần chấm hoặc một phiếu tăng ca. Ngày trích ra có thể là ngày lập/xác nhận, không nhất thiết ngày làm việc.

Host phải hiển thị ảnh và nguồn, cho người dùng sửa/bổ sung, bỏ xác nhận nếu giá trị hoặc ảnh nguồn đổi. Xuất bản đối chiếu không phải lệnh nhập công. Chỉ sau quy trình kiểm tra nghiệp vụ, quyền và chống trùng của host mới được ghi. Thư viện không xác minh chữ ký, không suy đoán giờ qua đêm, không tính giờ được trả lương và không tự học từ bản chưa duyệt.

Tên nhân viên hoặc các số trong nội dung OCR đều là đầu vào chưa tin cậy: UI phải escape văn bản; không dùng rawText làm HTML hoặc lệnh. Không đưa rawText, source hoặc ảnh vào log công khai. `canAutoImport=false` và `requiresReview=true` luôn được trả về, kể cả trường hợp không tìm được gợi ý.
