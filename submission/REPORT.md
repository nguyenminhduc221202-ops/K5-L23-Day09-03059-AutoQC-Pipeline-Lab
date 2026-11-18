# Báo cáo Day 09 — Nguyễn Minh Đức, 03059

## 1. Kết luận trước
Pipeline ra quyết định Hold (mã thoát 10). Từ 224 ảnh đầu vào, bước intake loại 21 ảnh lỗi/trùng/rò rỉ và nhận 203 ảnh; bản nháp 203 ảnh được xuất ra submission/export/clean_v1/. Nguyên nhân chính là sau khi máy tự sửa và người duyệt (ngân sách 80 ảnh) gán xong 6 ảnh thiếu file nhãn thì không còn lỗi bắt buộc nào (0 ERROR), nhưng hàng đợi có tới 125 ảnh nên vẫn còn 38/203 ảnh (18.72%) có cảnh báo chưa được xem, vượt ngưỡng 10.00% của cổng.

## 2. Lỗi và phân việc
Tổng hợp từ submission/reports/02_error_list_v1.txt (trên 203 ảnh sau intake, cộng 21 ảnh đã loại ở bước đầu):

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| BAD_CLASS_ID | 6 | Máy | ID lớp nằm ngoài 0..3, máy xóa dòng (drop_line) |
| BAD_CLASS_NAME | 2 | Máy | Tên lớp Person, Bus sai hoa/thường, máy sửa lại data.yaml |
| BAD_FORMAT | 3 | Máy | Dòng thiếu cột hoặc chứa nan/inf, máy xóa dòng |
| BAD_SIZE | 3 | Máy | Ảnh có cạnh ngắn dưới 250 px, loại ngay ở cửa vào |
| BOX_OUT_OF_IMAGE | 8 | Máy | Box tràn quá 0.002, máy cắt gọn về [0, 1] (clip_box) |
| BOX_ZERO | 4 | Máy | Box có chiều rộng hoặc cao <= 0, máy xóa dòng |
| CORRUPT_IMAGE | 2 | Máy | File ảnh hỏng không giải mã được, máy loại ảnh |
| DUP_BOX | 7 | Máy | Box lặp lại cùng lớp với dòng trước, máy xóa dòng |
| DUP_IMAGE_EXACT | 8 | Máy | Ảnh trùng từng byte (md5), máy loại bản trùng |
| DUP_IMAGE_NEAR | 3 | Máy | Ảnh trùng gần đúng (phash <= 8), máy loại bản trùng |
| LEAK_TEST | 5 | Máy | Ảnh trùng với kho test/val, máy loại để tránh rò rỉ |
| MISSING_LABEL_FILE | 6 | Người | Máy không tự bịa nhãn, đẩy lên đầu hàng đợi (NEEDS_LABEL) |
| BOX_HUGE | 3 | Người | Cảnh báo box chiếm quá 0.95 diện tích ảnh |
| BOX_TINY | 6 | Người | Cảnh báo box có cạnh ngắn dưới 12 px |
| CLASS_RARE | 4 | Người | Cảnh báo thống kê lớp xuất hiện ít ở cấp dataset |
| EMPTY_LABEL | 12 | Người | Cảnh báo file nhãn rỗng (cần kiểm tra là ảnh nền hay thiếu nhãn) |
| POSSIBLE_FALSE_POS | 29 | Người | Cảnh báo box nhãn không khớp dự đoán của model thứ hai |
| POSSIBLE_LOOSE_BOX | 28 | Người | Cảnh báo box nhãn có dấu hiệu lệch hoặc lỏng |
| POSSIBLE_MISSING | 53 | Người | Cảnh báo model thấy vật thể nhưng nhãn chưa có box |
| POSSIBLE_WRONG_CLASS | 18 | Người | Cảnh báo nghi gán nhầm sang lớp hợp lệ khác |

File 05_review_queue.csv sắp thứ tự dựa trên tổng trọng số trong configs/pipeline.yaml. Ảnh img_0020 đứng đầu (priority 11.524) vì vừa bị xóa dòng lỗi vừa kèm nhiều cảnh báo, ngay sau đó là 6 ảnh NEEDS_LABEL (priority 10.0) để đảm bảo các ca thiếu file nhãn được xử lý trước. Phần còn lại được xếp theo mức độ nghi ngờ ngữ nghĩa (POSSIBLE_WRONG_CLASS trọng số 3, POSSIBLE_MISSING và POSSIBLE_FALSE_POS trọng số 2, POSSIBLE_LOOSE_BOX trọng số 1.5). Với ngân sách 80 ảnh, người duyệt xem hết 6 ca NEEDS_LABEL và 74 ảnh ưu tiên cao nhất trong 119 ảnh cảnh báo còn lại.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| duplicates.phash_dist | 2 | 8 | DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67 (F1 0.67 → 0.80) | Tăng recall so với 2 nhưng giữ mức an toàn, tránh gộp nhầm ảnh khác nhau như khi tăng lên 16 |
| second_opinion.conf | 0.25 | 0.6 | WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; MISSING: 0.50 / 1.00 → 0.57 / 1.00 | Giảm bớt cảnh báo giả so với 0.25 mà vẫn giữ recall 1.00 cho MISSING (ở 0.8 bị tụt xuống 0.75) |

Chỗ calibration dễ đánh lừa nhất là kích thước nhỏ của tập data/calib/ (chỉ có 39 ảnh). Trên tập này các ảnh khá tách biệt nên phash_dist = 16 đạt F1 cao nhất (0.91) mà không bị bắt nhầm, nhưng nếu áp thẳng lên 224 ảnh thật rất dễ loại oan ảnh hợp lệ. Khi hạ xuống phash_dist = 8 và kiểm tra lại 01_intake.txt, pipeline chỉ loại đúng 3 ảnh DUP_IMAGE_NEAR (img_0076 và img_0143 có phash 0; img_0223 có phash 6), hợp lý với dữ liệu thực tế.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- Chứng minh gate chặn đúng: khi chạy python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb (không có người duyệt nên 6 ảnh MISSING_LABEL_FILE vẫn còn nguyên), pipeline kết luận Rework với 6 lỗi bắt buộc, trả về mã thoát 20 và không xuất dataset.
- Hai điểm mù pipeline không bắt được:
  1. Trường hợp cả nhãn gốc lẫn model yolo26l đều gán nhầm lớp hoặc cùng bỏ sót vật thể nhỏ (< 600 px²), second_opinion sẽ im lặng.
  2. Các box chỉ hơi lỏng (IoU >= 0.5 so với dự đoán) hoặc các cặp ảnh trùng đã bị cắt/xoay/đổi sáng mạnh làm phash_dist > 8 vẫn có thể lọt qua bộ lọc.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Thử nghiệm chạy local trên GPU RTX 3070 Ti với yolo26n.pt, 20 epoch, imgsz=640, batch=16, 2 seed (0 và 1), đánh giá trên cùng tập gold_val (40 ảnh) và test (100 ảnh):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.697 ± 0.028 | 0.507 ± 0.014 | 0.784 ± 0.052 | 0.605 ± 0.048 |
| clean | 203 | 2 | 0.695 ± 0.012 | 0.474 ± 0.001 | 0.758 ± 0.010 | 0.594 ± 0.008 |

Chênh lệch mAP50 (clean − raw) là -0.002, nhỏ hơn rất nhiều so với độ lệch chuẩn giữa các seed (± 0.028 ở raw và ± 0.012 ở clean). Nói cách khác, khác biệt này nằm gọn trong nhiễu ngẫu nhiên nên chưa thể kết luận bộ clean cho mAP cao hơn raw; điểm tích cực rõ nhất là kết quả trên clean ổn định hơn hẳn giữa các seed (độ lệch mAP50-95 chỉ còn ± 0.001).

Hai giả thuyết giải thích kết quả này:
1. Tập raw bị rò rỉ 5 ảnh trùng với data/test/ (img_0049, img_0101, img_0167, img_0174, img_0221), khiến điểm đánh giá của raw trên tập test bị kéo lên giả tạo. Có thể kiểm chứng bằng cách đánh giá lại trên 95 ảnh test đã bỏ 5 ảnh trùng.
2. Tập clean ít hơn 21 ảnh, lại đang ở trạng thái Hold (vẫn còn 38/203 ảnh cảnh báo chưa qua người duyệt) và 20 epoch còn hơi ngắn để model hội tụ hết. Có thể kiểm chứng bằng cách duyệt hết 38 ảnh còn lại để đạt Release rồi train lại ở 50–100 epoch.

## 6. Quyết định và ghi chú AI
- Quyết định cuối: giữ nguyên Hold, chưa phát hành tự động. Để chuyển thành Release, cần tăng ngân sách duyệt lên khoảng 100 ảnh (thêm ~20 ảnh) để kéo tỉ lệ ảnh cảnh báo chưa duyệt từ 18.72% xuống dưới 10.00%, hoặc rà soát lại các cảnh báo EMPTY_LABEL / BOX_TINY trong hàng đợi.
- Ghi chú dùng AI:
  - Prompt chính: nhờ hướng dẫn từng bước theo tài liệu lab và viết khung 4 module (label_format, gate, autofix, second_opinion) đúng đặc tả docstring.
  - Cách kiểm tra: chạy pytest cho từng module, chạy đủ 79–83 test, rồi chạy pipeline.calibrate và pipeline.run đối chiếu trực tiếp với báo cáo sinh ra.
  - Điểm cần tự kiểm khi dùng AI: lúc một dòng nhãn dính đồng thời BOX_OUT_OF_IMAGE và DUP_BOX, phải kiểm tra kỹ để autofix chỉ xóa dòng (drop_line) chứ không ghi thêm clip_box, đồng thời giữ đúng số dòng gốc khi file có dòng trống.
