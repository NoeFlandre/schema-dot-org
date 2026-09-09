import json
import sys

from scripts.render_types import main, read_types, render, shown_types


def test_shown_types_keeps_top_forty_and_folds_the_remainder():
    counts = {f"Type{index:02d}": 100 - index for index in range(42)}
    assert shown_types(counts) == [
        *[(f"Type{index:02d}", 100 - index) for index in range(40)],
        ("Other", 119),
    ]


def test_shown_types_breaks_ties_by_label():
    assert shown_types({"Zoo": 2, "Alpha": 2, "Beta": 1}) == [
        ("Alpha", 2),
        ("Zoo", 2),
        ("Beta", 1),
    ]


def test_read_types_loads_the_complete_mapping(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"types": {"Place": 4, "Hotel": 2}}), encoding="utf-8")
    assert read_types(path) == {"Place": 4, "Hotel": 2}


def test_render_writes_a_png_and_returns_its_bars(tmp_path):
    output = tmp_path / "types.png"
    assert render({"Restaurant": 3, "Cafe": 1}, output) == [
        ("Restaurant", 3),
        ("Cafe", 1),
    ]
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_render_handles_no_type_assignments(tmp_path):
    output = tmp_path / "empty.png"
    assert render({}, output) == []
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_main_prints_a_summary(tmp_path, monkeypatch, capsys):
    stats = tmp_path / "stats.json"
    output = tmp_path / "types.png"
    stats.write_text(json.dumps({"types": {"Place": 4}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["render_types.py", str(stats), "--out", str(output)])
    main()
    assert json.loads(capsys.readouterr().out) == {
        "type_labels": 1,
        "type_assignments": 4,
        "bars": 1,
        "out": str(output),
    }
