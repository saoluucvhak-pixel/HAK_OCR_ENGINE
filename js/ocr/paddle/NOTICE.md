# Bộ ký tự PaddleOCR

- `ppocrv5_latin_dict.txt` — chép nguyên từ PaddleOCR (`ppocr/utils/dict/ppocrv5_latin_dict.txt`, commit `dab3fe3`, PaddlePaddle Authors, giấy phép Apache-2.0). Trùng từng dòng với bộ ký tự trong `inference.yml` của model `latin_PP-OCRv5_mobile_rec`. Giữ nguyên cả 64 dòng trùng và 2 ký tự không NFC (Ω, Å) vì thứ tự dòng = chỉ số lớp đầu ra của model.
- `vi_latin_dict.txt` — sinh bằng `js/scripts/paddle/vi-charset.cjs`: 836 dòng latin giữ nguyên thứ tự + 90 chữ Việt còn thiếu (ả ạ ằ … ỵ, cả chữ hoa) thêm vào cuối = 926 dòng. Dùng làm `Global.character_dict_path` khi huấn luyện lại model nhận dạng tiếng Việt; các lớp cũ tái dùng trọng số có sẵn, 90 lớp mới học từ đầu.

Model gốc chưa huấn luyện lại đọc đúng tuyệt đối 11/100 dòng họ tên / nhãn tiếng Việt in (thiếu chữ có dấu nặng / dấu chồng), nên không dùng thay Tesseract cho chữ tiếng Việt.
