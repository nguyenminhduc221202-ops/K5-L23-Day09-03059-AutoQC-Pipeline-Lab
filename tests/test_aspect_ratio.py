from pipeline.checks import aspect_ratio


def test_normal_aspect_ratio_is_clean(make_ds, cfg):
    ds = make_ds(images={"a": 1}, labels={"a": ["0 0.5 0.5 0.2 0.2", "1 0.5 0.5 0.4 0.1"]}, size=(640, 480))
    assert aspect_ratio.run(ds, cfg) == []


def test_extreme_wide_and_tall_boxes(make_ds, cfg):
    # 640x480: 0.5*640=320px, 0.02*480=9.6px -> ratio 33.3 > 10
    # 0.02*640=12.8px, 0.5*480=240px -> ratio 18.75 > 10
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["0 0.5 0.5 0.5 0.02", "1 0.5 0.5 0.02 0.5"]},
        size=(640, 480),
    )
    iss = aspect_ratio.run(ds, cfg)
    assert [(i.code, i.severity, i.line) for i in iss] == [
        ("BOX_EXTREME_ASPECT", "warn", 1),
        ("BOX_EXTREME_ASPECT", "warn", 2),
    ]


def test_bad_and_blank_lines_do_not_crash(make_ds, cfg):
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["garbage", "", "0 0.5 0.5 0 0.2", "1 0.5 0.5 0.5 0.02"]},
        size=(640, 480),
    )
    iss = aspect_ratio.run(ds, cfg)
    assert [(i.code, i.line) for i in iss] == [("BOX_EXTREME_ASPECT", 4)]


def test_threshold_comes_from_config(make_ds, cfg):
    cfg["aspect_ratio"] = {"max_ratio": 40.0}
    ds = make_ds(images={"a": 1}, labels={"a": ["0 0.5 0.5 0.5 0.02"]}, size=(640, 480))
    assert aspect_ratio.run(ds, cfg) == []
