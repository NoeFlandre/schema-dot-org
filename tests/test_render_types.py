from scripts.render_types import render, shown_types


def test_shown_types_keeps_top_twenty_and_folds_the_remainder():
    counts = {f"Type{index:02d}": 100 - index for index in range(22)}
    assert shown_types(counts) == [
        *[(f"Type{index:02d}", 100 - index) for index in range(20)],
        ("Other", 159),
    ]


def test_render_writes_a_png_and_returns_its_bars(tmp_path):
    output = tmp_path / "types.png"
    assert render({"Restaurant": 3, "Cafe": 1}, output) == [
        ("Restaurant", 3),
        ("Cafe", 1),
    ]
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
