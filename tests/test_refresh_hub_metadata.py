import gzip
import json
import sys
from dataclasses import asdict

from scripts.refresh_hub_metadata import main

from wdcgeo.extract import GeoText


def test_refresh_writes_stats_card_and_type_plot(tmp_path, monkeypatch):
    source = tmp_path / "part.jsonl.gz"
    record = GeoText(
        page_url="http://example.com/p/1",
        host="example.com",
        latitude=48.5,
        longitude=2.5,
        types=("Restaurant",),
        name="Cafe",
        description=None,
        address=None,
        text_properties=("name",),
        languages=("fr",),
    )
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record)) + "\n")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({"records": 2, "duplication": {"distinct_places": 1}}), encoding="utf-8"
    )
    output = tmp_path / "metadata"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh_hub_metadata.py",
            str(source),
            "--profile",
            str(profile),
            "--out",
            str(output),
        ],
    )

    main()

    stats = json.loads((output / "stats.json").read_text(encoding="utf-8"))
    assert stats["records"] == 1
    assert stats["input"] == {"records": 2, "distinct_places": 1}
    assert (output / "types.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    card = (output / "README.md").read_text(encoding="utf-8")
    assert "![Distribution of schema.org types](types.png)" in card
