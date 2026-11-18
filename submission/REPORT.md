# Báo cáo Day 09 — Nguyễn Minh Đức, 03059

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát `10`). Lô đầu vào có **224** ảnh; bước intake loại **21** ảnh lỗi/trùng/rò rỉ, nhận **203** ảnh và xuất bản nháp **203** ảnh ra `submission/export/clean_v1/`. Lý do chính: sau khi sửa tự động và người duyệt (ngân sách **80** ảnh) xử lý 6 ảnh thiếu file nhãn, toàn bộ lỗi bắt buộc (`ERROR`) đã về **0**, nhưng hàng đợi có tới **125** ảnh nên vẫn còn **38/203 (18.72%)** ảnh cảnh báo chưa được duyệt, vượt ngưỡng `warn_ratio_hold = 10.00%`.

## 2. Lỗi và phân việc
Số liệu lấy từ `submission/reports/02_error_list_v1.txt` (203 ảnh sau intake, cộng 21 ảnh loại ở intake):

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| `BAD_CLASS_ID` | 6 | Máy | ID lớp ngoài `0..3` → máy xóa dòng (`drop_line`) |
| `BAD_CLASS_NAME` | 2 | Máy | Tên lớp `Person`, `Bus` sai hoa/thường → máy sửa `data.yaml` |
| `BAD_FORMAT` | 3 | Máy | Thiếu cột hoặc `nan/inf` → máy xóa dòng (`drop_line`) |
| `BAD_SIZE` | 3 | Máy | Cạnh ngắn `< 250px` → máy loại ảnh ở cửa vào |
| `BOX_OUT_OF_IMAGE` | 8 | Máy | Box tràn quá `0.002` → máy cắt về `[0, 1]` (`clip_box`) |
| `BOX_ZERO` | 4 | Máy | Box rộng hoặc cao `<= 0` → máy xóa dòng (`drop_line`) |
| `CORRUPT_IMAGE` | 2 | Máy | Ảnh hỏng không đọc/decode được → máy loại ảnh |
| `DUP_BOX` | 7 | Máy | Box trùng lặp cùng lớp → máy xóa dòng (`drop_line`) |
| `DUP_IMAGE_EXACT` | 8 | Máy | Trùng byte (md5) → máy loại ảnh trùng |
| `DUP_IMAGE_NEAR` | 3 | Máy | Trùng gần đúng (`phash <= 8`) → máy loại ảnh trùng |
| `LEAK_TEST` | 5 | Máy | Trùng ảnh trong `test/val` → máy loại để chống rò rỉ |
| `MISSING_LABEL_FILE` | 6 | Người | Máy không tự bịa nhãn → đẩy lên đầu hàng đợi (`NEEDS_LABEL`) |
| `BOX_HUGE` | 3 | Người | Cảnh báo box chiếm `> 0.95` diện tích ảnh |
| `BOX_TINY` | 6 | Người | Cảnh báo box cạnh ngắn `< 12px` |
| `CLASS_RARE` | 4 | Người | Cảnh báo thống kê lớp hiếm cấp dataset |
| `EMPTY_LABEL` | 12 | Người | Cảnh báo file nhãn rỗng (ảnh nền hay thiếu nhãn) |
| `POSSIBLE_FALSE_POS` | 29 | Người | Cảnh báo box nhãn không khớp dự đoán model |
| `POSSIBLE_LOOSE_BOX` | 28 | Người | Cảnh báo box nhãn lệch/lỏng so với model |
| `POSSIBLE_MISSING` | 53 | Người | Cảnh báo model thấy vật nhưng nhãn thiếu box |
| `POSSIBLE_WRONG_CLASS` | 18 | Người | Cảnh báo nghi nhầm lớp hợp lệ |

`05_review_queue.csv` xếp ảnh theo tổng trọng số mức độ nghiêm trọng trong `configs/pipeline.yaml`: ảnh có `FIXED_DROP_LINE` kèm nhiều cảnh báo (`img_0020`, priority `11.524`) và 6 ảnh `NEEDS_LABEL` (priority `10.0`) đứng đầu để bảo đảm sửa hết lỗi nặng/thiếu nhãn trước; tiếp theo là các ảnh nhiều cảnh báo ngữ nghĩa (`POSSIBLE_WRONG_CLASS` trọng số `3`, `POSSIBLE_MISSING`/`POSSIBLE_FALSE_POS` trọng số `2`, `POSSIBLE_LOOSE_BOX` trọng số `1.5`). Với ngân sách **80 ảnh**, người duyệt xem được toàn bộ 6 ca `NEEDS_LABEL` và 74 ảnh ưu tiên cao nhất trong 119 ảnh cảnh báo còn lại (còn 38 ảnh chưa duyệt ở vòng 3).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | `2` | **`8`** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (F1 `0.67 → 0.80`) | Tăng recall so với `2`, tránh rủi ro gộp nhầm ảnh khác nhau như khi đẩy lên `16` |
| `second_opinion.conf` | `0.25` | **`0.6`** | `WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83`; `MISSING`: `0.50 / 1.00` → `0.57 / 1.00` | Giảm cảnh báo giả so với `0.25` mà vẫn giữ `Recall = 1.00` cho `MISSING` (không bị tụt xuống `0.75` như ở `0.8`) |

**Chỗ calibration có thể đánh lừa:** Bộ `data/calib/` chỉ có **39 ảnh**, các ảnh nền khác nhau rõ rệt nên `phash_dist = 16` đạt F1 cao nhất (`0.91`) trên `calib` mà không có false positive. Tuy nhiên trên lô thật **224 ảnh**, đặt ngưỡng quá rộng dễ loại nhầm ảnh hợp lệ. Khi chọn `phash_dist = 8` và kiểm tra `01_intake.txt`, pipeline chỉ loại đúng 3 ảnh `DUP_IMAGE_NEAR` (`img_0076` và `img_0143` có `phash = 0`; `img_0223` có `phash = 6`), hợp lý và an toàn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **(a) Chứng minh gate chặn đúng:** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên 6 ảnh `MISSING_LABEL_FILE` còn nguyên). Pipeline kết luận **`REWORK — còn 6 lỗi bắt buộc (ERROR)`**, mã thoát **`20`**, và **không xuất** dataset (`KHÔNG xuất: còn lỗi bắt buộc (Rework)`).
- **(b) Điểm mù pipeline không bắt được:**
  1. **Lỗi ngữ nghĩa mà model lớn cũng sai/bỏ sót:** Nếu cả nhãn gốc và `yolo26l` đều nhận nhầm lớp hoặc bỏ qua vật thể nhỏ (`< 600 px²`), `second_opinion` không phát cảnh báo.
  2. **Box lỏng nhẹ hoặc ảnh trùng biến đổi mạnh:** Box có `IoU >= 0.5` so với dự đoán (chưa dưới ngưỡng `iou_loose = 0.5`) vẫn lọt qua; các ảnh trùng bị cắt mạnh/xoay/đổi sáng lớn khiến `phash_dist > 8` cũng không bị `duplicates` bắt.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
chạy trên RTX 3070 Ti với `yolo26n.pt`, `20` epoch, `imgsz=640`, `batch=16`, `2` seed (`0`, `1`), đánh giá công bằng trên cùng `gold_val` (40 ảnh) và `test` (100 ảnh):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---:|---:|---|---|---|---|
| `raw` | 224 | 2 | 0.697 ± 0.028 | 0.507 ± 0.014 | 0.784 ± 0.052 | 0.605 ± 0.048 |
| `clean` | 203 | 2 | 0.695 ± 0.012 | 0.474 ± 0.001 | 0.758 ± 0.010 | 0.594 ± 0.008 |

- **So sánh với nhiễu giữa seed & kết luận trung thực:** Chênh lệch mAP50 (`clean − raw`) là **`-0.002`**, nhỏ hơn nhiều so với độ lệch chuẩn giữa các seed (`± 0.028` ở `raw` và `± 0.012` ở `clean`). Do đó **chưa thể kết luận** bộ `clean` cho mAP cao hơn `raw` (khác biệt nằm hoàn toàn trong nhiễu ngẫu nhiên của seed); tuy nhiên độ dao động giữa các seed của `clean` giảm rõ rệt (đặc biệt `mAP50-95` ổn định ở `± 0.001`).
- **Giả thuyết giải thích & cách kiểm:**
  1. **Rò rỉ tập test trong `raw` (`LEAK_TEST`):** `raw` chứa **5** ảnh trùng với `data/test/` (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`), làm điểm test của `raw` bị thổi phồng giả tạo. *Cách kiểm:* đánh giá lại trên 95 ảnh `test` sau khi bỏ 5 ảnh trùng.
  2. **Số lượng ảnh ít và dữ liệu còn ở trạng thái `Hold`:** `clean` còn 203 ảnh (ít hơn 21 ảnh) và vẫn còn **38/203** ảnh cảnh báo chưa qua người duyệt, cộng thêm `20` epoch khá ngắn nên model chưa hội tụ hết. *Cách kiểm:* duyệt nốt 38 ảnh để đạt `Release` và train dài hơn (50–100 epoch).

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối:** **Hold** — không phát hành tự động ngay. Để chuyển thành **Release**, cần tăng ngân sách duyệt người thêm ít nhất ~20 ảnh (từ 80 lên ~100 ảnh) để đưa tỉ lệ ảnh cảnh báo chưa duyệt từ `18.72%` xuống dưới `10.00%`, hoặc rà soát lại các ảnh cảnh báo `EMPTY_LABEL` / `BOX_TINY` còn lại trong hàng đợi.
- **(b) Ghi chú AI:**
  - *Prompt chính:* Yêu cầu hướng dẫn từng bước và viết khung 4 module (`label_format`, `gate`, `autofix`, `second_opinion`) đúng theo docstring và các ca biên trong test.
  - *Cách kiểm code:* Chạy `pytest` cho từng module (`test_label_format`, `test_gate`, `test_autofix`, `test_second_opinion`), chạy full 79 tests, rồi chạy `pipeline.calibrate` và `pipeline.run` kiểm tra log thực tế.
  - *Lưu ý/lỗi cần kiểm:* Khi một dòng vừa bị `BOX_OUT_OF_IMAGE` vừa `DUP_BOX`, `autofix` phải ưu tiên `drop_line` và không ghi thêm `clip_box`, đồng thời giữ đúng số dòng gốc khi file nhãn có dòng trống.
