# Dữ liệu ngôn ngữ OCR (Tesseract) — đóng gói kèm app, dùng offline

| File | Nguồn | Giấy phép | SHA-256 |
|---|---|---|---|
| lang/vie.traineddata.gz | npm `@tesseract.js-data/vie` (4.0.0_best_int) — tessdata_best của dự án Tesseract | Apache-2.0 | `2284f610f262a1b19ec8df9f196b9ff6ce38ddb4a66329e998941df4b8961c8d` |
| lang/eng.traineddata.gz | npm `@tesseract.js-data/eng` (4.0.0_best_int) | Apache-2.0 | `45b4cb346724ac1774f1c36f42f182b887bcdb28ebe63e6fff90ac41f3fcff91` |

Dùng bởi `main/ocr-service.js` (tesseract.js 5.1.1, Apache-2.0). Thư mục này nằm ngoài asar (`build.asarUnpack`).
