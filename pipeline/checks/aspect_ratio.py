"""CHECK THƯỞNG — Kiểm tra box lệch tỉ lệ khung hình (aspect ratio quá lớn).

Test: pytest tests/test_aspect_ratio.py -q
"""
from ..common import WARN, Issue, parse_yolo_line


def run(ds, cfg):
    max_ratio = cfg.get("aspect_ratio", {}).get("max_ratio", 10.0)
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)
        if size is None:
            continue
        W, H = size
        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                cid, _, _, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if not (0 <= cid < len(ds.classes)) or w <= 0 or h <= 0:
                continue
            w_px, h_px = w * W, h * H
            ratio = max(w_px / h_px, h_px / w_px)
            if ratio > max_ratio:
                issues.append(
                    Issue(
                        "aspect_ratio",
                        WARN,
                        "BOX_EXTREME_ASPECT",
                        stem,
                        f"tỉ lệ khung hình bất thường ({ratio:.1f} > {max_ratio})",
                        line=line_no,
                        extra={"aspect": round(ratio, 2)},
                    )
                )
    return issues
