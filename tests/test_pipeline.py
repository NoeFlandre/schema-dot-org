import gzip

from wdcgeo.pipeline import Pipeline

PAGE = "http://example.com/p/1"
S = "http://schema.org/"
QUADS = [
    f'_:place <{S}name> "Cafe Zero" <{PAGE}> .',
    f'_:place <{S}latitude> "48.0" <{PAGE}> .',
    f'_:place <{S}longitude> "2.0" <{PAGE}> .',
]


def write(directory, name, lines):
    path = directory / name
    text = "".join(f"{line}\n" for line in lines)
    if name.endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return str(path)


def test_runs_every_location_through_parsing_and_extraction(tmp_path):
    other = [line.replace(PAGE, "http://other.example.com/p/2") for line in QUADS]
    pipeline = Pipeline([write(tmp_path, "a.gz", QUADS), write(tmp_path, "b.txt", other)])
    assert [record.host for record in pipeline.records()] == [
        "example.com",
        "other.example.com",
    ]


def test_counts_lines_quads_and_the_lines_it_could_not_parse(tmp_path):
    pipeline = Pipeline([write(tmp_path, "a.gz", [*QUADS, "not a quad"])])
    assert pipeline.counts() == {"locations": 1, "lines": 0, "quads": 0, "unparsed_lines": 0}
    list(pipeline.records())
    assert pipeline.counts() == {"locations": 1, "lines": 4, "quads": 3, "unparsed_lines": 1}


def test_stops_after_max_lines_across_locations(tmp_path):
    first = write(tmp_path, "a.gz", QUADS)
    second = write(
        tmp_path, "b.gz", [line.replace(PAGE, "http://other.example.com/") for line in QUADS]
    )
    pipeline = Pipeline([first, second], max_lines=4)
    records = list(pipeline.records())
    assert [record.host for record in records] == ["example.com"]
    assert pipeline.counts()["lines"] == 4


def test_reads_everything_when_max_lines_is_not_set(tmp_path):
    pipeline = Pipeline([write(tmp_path, "a.gz", QUADS)])
    list(pipeline.records())
    assert pipeline.counts()["lines"] == 3


def test_does_not_open_a_location_it_will_not_read(tmp_path):
    pipeline = Pipeline([str(tmp_path / "absent.gz")], max_lines=0)
    assert list(pipeline.records()) == []
    assert pipeline.counts()["lines"] == 0


def test_does_not_open_the_next_location_once_the_cap_is_reached(tmp_path):
    reached = write(tmp_path, "a.gz", QUADS)
    pipeline = Pipeline([reached, str(tmp_path / "absent.gz")], max_lines=3)
    assert len(list(pipeline.records())) == 1
