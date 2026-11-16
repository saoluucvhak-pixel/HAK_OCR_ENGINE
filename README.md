# HAK_OCR_ENGINE — HAK Smart OCR AI

Repo chung cho OCR của HAK Group: đọc ảnh/PDF chứng từ (bảng chấm công, phiếu cân, phiếu chi…) **offline**, kết quả luôn qua bước người duyệt.

## Nguồn và thay đổi

- Mã nguồn chính chuyển nguyên trạng từ `LUONG_HAK`, nhánh `feature/hak-smart-ocr-ai-windows`, thư mục `apps/hak-smart-ocr-ai/` (commit `ec390c0`), đưa lên gốc repo này. Workflow Windows đã sửa đường dẫn tương ứng.
- **Thêm** `hak_ocr/office.py` + lệnh `cli.py office`: đọc Word/Excel/PowerPoint/HTML/CSV ra Markdown bằng [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft, MIT). Chỉ file cục bộ, không mở URL. Cài thêm: `pip install -r requirements-office.txt`.
- **Thêm** `hak_ocr/unlimited_engine.py` + lệnh `cli.py unlimited-ocr`: adapter tùy chọn cho [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) (Baidu, MIT), theo đúng quy tắc engine nâng cao: bắt buộc model cục bộ `vendor/models/unlimited_ocr`, không tự tải, cần GPU NVIDIA, kết quả là gợi ý chưa duyệt. Chưa kiểm chứng chất lượng tiếng Việt.
- Bản `hak_ocr` thử nghiệm trước đó của repo này (nhánh `feat/ocr-engine`, chưa từng lên GitHub) **đã bỏ**, vì bản Smart OCR AI làm tốt hơn mọi phần trừ đọc file văn phòng — phần đó đã chuyển thành `office.py`.
- **Thêm** thư mục `js/`: bộ OCR JavaScript chạy bên trong app Electron, chuyển từ `LuongHAK_Offline` (Tesseract.js, gói tiếng Việt đóng kèm, tìm lưới bảng chấm công, **học từ chỗ người dùng sửa**). Xem `js/README.md`. Repo này giờ là nơi duy nhất chứa OCR của HAK — cả Python lẫn JavaScript.

```bash
python cli.py check                         # kiểm tra Tesseract + gói tiếng Việt
python cli.py import-and-ocr bangcong.jpg   # OCR ảnh/PDF vào kho cục bộ
python cli.py office bang-luong.xlsx        # Excel/Word/PowerPoint -> Markdown
python cli.py unlimited-ocr --check         # trạng thái Unlimited-OCR (model, thư viện, GPU)
cd js && npm install && npm test            # bản JavaScript cho app Electron
```

---

# HAK Smart OCR AI — Windows deployment

- For Windows Actions build, see `.github/workflows/hak-smart-ocr-ai-windows.yml` at the repository root of this branch.
- The default build bundles **Tesseract OCR** and Vietnamese/English language data. **PaddleOCR, Docling, UVDoc, TrOCR weights** are NOT bundled, benchmarked or claimed functional in this installer.
- `python -m pytest tests -q` performs automated source tests, not Windows acceptance.
- Actions artifact can be downloaded from the successful workflow run; frozen self-test is required, but visual Windows GUI acceptance remains separate.
- Do not upload real employee images, conversations, contracts, payroll, financial documents, private models, credentials, or data exports to this PUBLIC repo.

## Windows release

After pushes to this feature branch affecting this directory or the workflow, GitHub Actions will run on a Windows runner. If everything passes, download the artifact named `HAKSmartOCRAI-Windows-x64-1.2.0-alpha` containing a portable ZIP and an Inno Setup EXE installer. If the workflow fails, do not distribute installer; review the logs and fix the failure.

This release is **Alpha** and cannot automatically post OCR output into payroll without human review.

---

# HAK Smart OCR AI 1.1.0 — Hybrid Offline Code Release

**Start here:** `QUICKSTART_1.1.0.md`, `CHANGELOG_1.1.0.md`, and
`validation/TEST_REPORT_1.1.0.md`. This ZIP contains source code and tests,
**not** a Windows EXE or trained AI models. PaddleOCR/Docling/UVDoc/TrOCR
inference requires explicitly prepared local model folders and matching wheels.

**New:** hybrid OCR (unverified disagreements), Docling layout for PDF,
planar perspective, optional UVDoc curved preview, handwriting crop candidates,
rule-based/GGUF local evidence review and editable OCR chat text preserving
original. Do not use unverified OCR output directly for payroll or transfers.

---

# HAK SMART OCR AI — Windows Offline Desktop 1.0.2 MVP

**Đây là mã nguồn MVP có thể chạy sau khi cài các thư viện và Tesseract**, không phải file EXE đã biên dịch và nghiệm thu trên Windows. Đây là bản xây dựng thử nghiệm đầu tiên (MVP), không phải một hệ thống Document AI đã đạt đầy đủ đặc tả doanh nghiệp 1.0.

## 1. Các tính năng đã viết thành mã nguồn

- Giao diện PySide6: nhập JPG/JPEG/PNG/TIF/TIFF/BMP/PDF, thư viện tài liệu, xem ảnh/PDF, xử lý OCR trong QThread.
- Sao chép file gốc bất biến vào kho cục bộ, xác minh ảnh, phát hiện trùng SHA-256 và lưu SQLite/WAL.
- PDF text native: ưu tiên lấy lớp chữ có tọa độ qua PyMuPDF khi đủ dữ liệu; PDF scan / ảnh: dùng Tesseract với tiếng Việt và tiếng Anh.
- OCR xoay ảnh (OSD + fallback 0/90/180/270), tiền xử lý ảnh OpenCV và phân tích bảng kẻ ô bằng OpenCV.
- **OCR sâu từng ô** kết hợp hình dạng nét số 1, nhiều cấu hình Tesseract và nhận dạng tiêu đề; mọi ô AI điền được gắn nhãn gợi ý, KHÔNG được tự động duyệt.
- Review Studio: xem trang gốc, highlight vùng dữ liệu/ô, sửa trường và sửa trực tiếp ô bảng, thêm/xóa hàng/cột, lưu kết quả đã duyệt.
- Template Studio: mẫu trích xuất có cấu trúc bằng regex JSON cục bộ; cung cấp mẫu kỳ chấm công.
- Learning Center: lưu lịch sử sửa, tạo quy tắc ở trạng thái PROPOSED; chỉ cho phép TESTED nếu có ít nhất 3 chứng từ đối chứng khác đã duyệt và không xung đột. APPROVED/ACTIVE bằng thao tác người dùng. Quy tắc ACTIVE chỉ gợi ý, **không ghi đè số liệu**.
- Kiểm tra tổng theo ngày nếu bảng có tiêu đề ngày và cột tổng xác định rõ, giữ phân biệt `ô trống ≠ 0`.
- Xuất XLSX, JSON, CSV, TXT; chống spreadsheet formula injection; file chưa duyệt cần người dùng chấp nhận trước khi xuất.
- Sao lưu ZIP đầy đủ CSDL và ảnh gốc, manifest SHA-256; phục hồi qua CLI vào thư mục rỗng.
- Bộ kiểm thử tự động cho CSDL, OCR PDF native, learning rule, backup, mẫu, bảng, export và bảo toàn dữ liệu đã duyệt.

## 2. Khởi chạy từ mã nguồn trên Windows

Trên máy chuẩn bị, dùng **Python 3.11 x64** và cài Tesseract 5 + file ngôn ngữ `vie.traineddata`, `eng.traineddata` (từ nguồn đáng tin cậy, tuân thủ giấy phép).

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe cli.py check
.venv\Scripts\python.exe run.py
```

Nếu Windows sử dụng bản Tesseract portable đi kèm chương trình thì đặt các file của bộ cài vào `vendor/tesseract/`; quá trình chạy không tải model từ Internet. Khi chạy source trực tiếp, Tesseract cài vào PATH vẫn được hỗ trợ.

### Chạy OCR không cần giao diện

```powershell
.venv\Scripts\python.exe cli.py check
.venv\Scripts\python.exe cli.py import-and-ocr "C:\Documents\bangcong.jpg"
.venv\Scripts\python.exe cli.py import-and-ocr "C:\Documents\bangcong.jpg" --deep-cells
.venv\Scripts\python.exe cli.py export <DOCUMENT_ID> --format xlsx
.venv\Scripts\python.exe cli.py backup "D:\backup-ocr.zip"
.venv\Scripts\python.exe cli.py restore "D:\backup-ocr.zip" --to "D:\HAK-OCR-Restored"
```

Dữ liệu mặc định lưu ở `%LOCALAPPDATA%\HAK\SmartOCRAI\`, không lưu bên trong thư mục cài EXE. Có thể đổi bằng biến môi trường `HAK_OCR_DATA_HOME`.

## 3. Hướng dẫn xây dựng bản cài EXE **OFFLINE**

**Chưa có file Windows EXE trong gói này.** Việc build EXE phải được thực hiện trên Windows 10/11 x64 cùng phiên bản Python đã lựa chọn.

1. Trên **máy build** có Internet, chạy `scripts/prepare_wheelhouse_windows.ps1` để chuẩn bị wheelhouse. Đặt một bản Tesseract x64 portable đầy đủ DLL và các `vie/eng.traineddata` vào `vendor/tesseract` (không có trong mã nguồn vì lý do bản quyền/phân phối).
2. Chuyển source + wheelhouse + `vendor/tesseract` sang máy build Windows offline. Chạy `scripts/build_windows.ps1`. Script cài wheel bằng `--no-index`, chạy unit test và đóng gói bằng PyInstaller.
3. Sau khi build thành công, chạy Inno Setup Compiler với file `scripts/HAKSmartOCRAI.iss` để tạo setup Windows.
4. Trên **máy Windows sạch, không Internet**, kiểm thử mở app, PDF native, ảnh scan tiếng Việt, OCR xoay, Excel, learning và sao lưu. Kiểm tra xem `vie.traineddata` được tìm thấy trong `dist`.

> Nếu muốn build để phân phối thương mại, cần xác minh giấy phép thư viện, model, Tesseract và đặc biệt là PyMuPDF (AGPL/thương mại). Không mặc nhiên được phép phân phối thương mại khi chưa giải quyết nghĩa vụ bản quyền.

## 4. Quy trình kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m compileall -q hak_ocr run.py cli.py
```

Khi nhập tài liệu thật, chỉ lấy dữ liệu từ trường/ô **đã kiểm duyệt** trước khi tính lương, ghi sổ hoặc thanh toán. Ảnh chữ viết tay, bảng cong phối cảnh, ô nhỏ nhiều số vẫn có thể sai. Không tự động xuất sang phần mềm lương.

## 5. Hạn chế còn tồn tại (phải hoàn thiện ở các phiên bản kế tiếp)

- Chưa tích hợp PaddleOCR, Docling, mô hình VLM hoặc quy trình fine-tuning thật. Engine OCR đang dùng **Tesseract CPU** + PDF native + OpenCV.
- Chưa phân tích liên chứng từ (tin nhắn ↔ bảng công ↔ dữ liệu vân tay ↔ bảng lương) tự động, chưa có pipeline hiểu ngữ nghĩa LLM offline.
- Bảng nhiều lớp tiêu đề/ô gộp, ảnh phối cảnh khó hoặc in mờ không bảo đảm tái tạo đúng; có thể xuất thiếu hàng/cột, cần người kiểm tra.
- Giao diện chưa có kéo vùng tọa độ để tạo template, không có zoom/pan tùy biến nâng cao, chưa Undo/Redo, chưa có PDF searchable xuất lại.
- Không có cơ chế mã hóa file sao lưu, mật khẩu mở PDF, đa người dùng, cấu hình phân quyền, batch queue dừng/tiếp tục chuyên sâu hoặc khôi phục crash giữa một job.
- Learning Engine hiện chỉ *lưu và gợi ý từ correction có kiểm thử*, không cập nhật trọng số model; quy tắc cho **ô bảng** không được kích hoạt vì chưa có bộ holdout bảng độc lập.
- Chưa build/test giao diện PySide6 trên máy Windows thật trong môi trường tạo source. Script build chưa được chạy trên Windows thật.

Bản này là nền tảng mã nguồn để tiếp tục triển khai theo đặc tả `HAK_Smart_OCR_AI_1.0_Dac_ta_ky_thuat.md`.

## 6. Phương pháp bảo đảm tính đúng đắn

Không dùng dữ liệu OCR chưa duyệt làm nguồn kế toán, chấm công hoặc chuyển tiền. Mỗi lần sửa được lưu nhật ký có `document_id`, `field_key`, trước/sau, người xác nhận và thời gian. Kiểm thử rule phải sử dụng các chứng từ khác biệt với nguồn học. Giữ bản tài liệu gốc và xuất trạng thái `NEEDS_REVIEW` nếu chưa được xác nhận.

**Bảo vệ dữ liệu:** bản sao lưu có chứa dữ liệu nhân sự, hồ sơ và ảnh nguyên gốc; lưu an toàn, chỉ chia sẻ với người có thẩm quyền. Không đính kèm ảnh chứng từ thật trong mã nguồn công khai.

## 7. Bổ sung ở bản MVP 1.0.1 (đối chiếu an toàn)

- Module `hak_ocr/attendance_audit.py`: tổng hợp mỗi nhân sự/chỉ tiêu theo ô số đã đọc, số ô trống, số ô OCR không hợp lệ, ngày trùng hoặc suy luận; lưu tham chiếu bounding box từng ô.
- Xuất Excel bổ sung `Doi_chieu_cong`: giải thích rõ tổng đọc được không phải tổng công hoàn chỉnh nếu còn ô trống; mọi kết quả đều `payroll_ready=false` cho đến khi có đối chiếu nghiệp vụ và phê duyệt bên ngoài.
- Hai kiểm thử độc lập thêm vào `tests/test_attendance_audit.py`, gồm chống formula injection trong báo cáo mới.
- Vẫn chưa có bằng chứng đạt accuracy trên toàn bộ 10 ảnh; vẫn chưa build được Windows EXE trong Linux.


## 8. Nâng cấp MVP 1.0.2 — số nhỏ, ngày tháng và an toàn xác nhận

- `deep_cells.py`: bổ sung phân loại hình dạng chữ số **1** hẹp trong ô số, lọc nhiễu biên, OCR nhiều cách và khôi phục tiêu đề đã nhìn thấy trên ảnh theo hai lần đọc. Chỉ sử dụng để **đề xuất OCR**, không suy diễn rằng người lao động thực sự có công.
- Mọi giá trị OCR sâu được lưu ở `Table.cell_suggestions` có tọa độ nguồn và phương pháp; UI tô vàng ô chưa duyệt, Excel có sheet `Goi_y_OCR`.
- `attendance.py`: tách nhãn ngày OCR gốc khỏi ngày suy luận, cảnh báo nhãn bị đọc nhầm, kiểm tra số ngày thực tế của kỳ (ví dụ tháng 9 có 30 ngày). Ngăn xác nhận toàn chứng từ nếu bảng công dạng dọc còn ngày suy luận chưa được sửa.
- `storage.py`: thêm `source_signature` cho sửa bảng, khóa duyệt theo hình học của lưới. Nếu OCR lại thay kích thước/vị trí lưới, phiên bản đã sửa trước đó được lưu trong SQLite nhưng KHÔNG đè lên bảng OCR mới. Cơ sở dữ liệu 1.0.1 tự migration; các bảng đã duyệt trước đây chưa có chữ ký nguồn sẽ phải được rà soát lại.
- `scripts/benchmark_table.py` và `validation/example_schedule_reference.json`: công cụ đánh giá từng ô bằng nhãn tham khảo riêng, chạy hoàn toàn offline. Tệp nhãn chỉ chứa giá trị, không đi kèm ảnh nhân sự.
- Kiểm thử `pytest`: **23/23 đạt** trên môi trường Linux (Python 3.13).
- Thử nghiệm ảnh lịch công 30 ngày được cung cấp: **60/60 ô công/cơm** khớp với cách đọc thủ công để làm nhãn tham chiếu; riêng nhãn cột ngày vẫn phải soát do OCR có ký tự nhầm. Đây **không phải** chỉ số chính xác trên nhiều mẫu, và nhãn tham chiếu này chưa phải dữ liệu chấm công đã được duyệt.

### Chạy benchmark theo tệp ảnh cục bộ

```powershell
.venv\Scripts\python.exe scripts/benchmark_table.py "C:\Samples\lich_cong.jpg" validation/example_schedule_reference.json --no-rotation
```

Chỉ sử dụng tệp nhãn mẫu trên đúng bố cục và nội dung lịch công tương ứng. Với ảnh khác, tự tạo nhãn đối chứng và lưu riêng theo cấu trúc JSON; không áp dụng nhãn mẫu cho ảnh khác.

**Giới hạn chưa thay đổi:** chưa test Windows EXE thật; chưa tích hợp PaddleOCR/Docling/LLM offline; chưa kiểm thử đạt chất lượng trên toàn bộ 10 ảnh.
