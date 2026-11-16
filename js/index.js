"use strict";
/**
 * HAK OCR (JavaScript) — điểm vào cho Node/Electron (tiến trình chính).
 * Trong trình duyệt/renderer: nạp từng file core/*.js bằng <script>, dùng window.HAKCore.{grid,tsparse,tsocr,ocrFeat,ocrLib,ocrLayout,ocrRules,ocrNameMemory,pdfText,ocrLearn}.
 */
module.exports = {
  grid: require("./core/table-grid.js"),               // tìm lưới bảng trong ảnh xám
  timesheetParse: require("./core/timesheet-parse.js"), // dựng bảng chấm công từ các ô đã đọc
  timesheetOcr: require("./core/timesheet-ocr.js"),     // điều phối: đoán chiều ảnh → tìm ô → OCR theo lô → bảng xem trước
  learning: {
    features: require("./core/ocr-learning/features.js"),
    library: require("./core/ocr-learning/library.js"),
    layout: require("./core/ocr-learning/layout.js"),
    rules: require("./core/ocr-learning/rules.js"),
    nameMemory: require("./core/ocr-learning/name-memory.js"),
    pdfText: require("./core/ocr-learning/pdf-text.js"),
  },
  createOcrService: (...a) => require("./main/ocr-service.js").createOcrService(...a), // Tesseract.js offline, gói vie/eng đóng kèm
  createOcrLibrary: (...a) => require("./main/ocr-library.js").createStore(...a),        // thư viện mẫu đã học, lưu bền trên đĩa
};
