"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


_DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
_REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]
    fixes = []
    removed = set()

    for i in errors:
        if i.code.startswith("DUP_IMAGE_") or i.code in _REMOVE_CODES:
            if i.image in removed:
                continue
            removed.add(i.image)
            ip = ds.image_path(i.image)
            if ip and ip.exists():
                ip.unlink()
            lp = ds.label_path(i.image)
            if lp.exists():
                lp.unlink()
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "remove_image",
                "before": i.code,
                "after": "(đã xoá)",
            })

    if any(i.code == "BAD_CLASS_NAME" for i in errors) and ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = str(data.get("names", ""))
        data["names"] = list(cfg["classes"])
        ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": before,
            "after": str(data["names"]),
        })

    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    per_file_drop = defaultdict(set)
    per_file_clip = defaultdict(set)
    for i in errors:
        if i.image in removed or i.line is None:
            continue
        if i.code in _DROP_CODES:
            per_file_drop[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            per_file_clip[i.image].add(i.line)

    for stem in sorted(set(per_file_drop) | set(per_file_clip)):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        drop_lines = per_file_drop[stem]
        clip_lines = per_file_clip[stem]
        new_lines = []
        for idx, text in enumerate(raw_lines, 1):
            if idx in drop_lines:
                fixes.append({
                    "image": stem,
                    "line": idx,
                    "action": "drop_line",
                    "before": text,
                    "after": "(đã xoá)",
                })
                continue
            if idx in clip_lines:
                try:
                    cid, cx, cy, w, h = parse_yolo_line(text)
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": text,
                        "after": "(đã xoá)",
                    })
                    continue
                x1 = max(0.0, min(1.0, cx - w / 2))
                y1 = max(0.0, min(1.0, cy - h / 2))
                x2 = max(0.0, min(1.0, cx + w / 2))
                y2 = max(0.0, min(1.0, cy + h / 2))
                nw, nh = x2 - x1, y2 - y1
                if nw <= 0 or nh <= 0:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": text,
                        "after": "(đã xoá: ngoài ảnh)",
                    })
                    continue
                ncx, ncy = (x1 + x2) / 2, (y1 + y2) / 2
                after = f"{cid} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                fixes.append({
                    "image": stem,
                    "line": idx,
                    "action": "clip_box",
                    "before": text,
                    "after": after,
                })
                new_lines.append(after)
            else:
                new_lines.append(text)
        lp.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes
