import gzip
import json

import pytest

from wdcgeo import cli
from wdcgeo.corpus import part_url

PAGE = "http://example.com/p/1"
S = "http://schema.org/"
HELP_TEXTS = [value for name, value in vars(cli).items() if name.endswith("_HELP")]


def source(directory, filename, page=PAGE, name="Cafe Zero"):
    lines = [
        f'_:place <{S}name> "{name}" <{page}> .',
        f'_:place <{S}latitude> "48.0" <{page}> .',
        f'_:place <{S}longitude> "2.0" <{page}> .',
    ]
    path = directory / filename
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("".join(f"{line}\n" for line in lines))
    return str(path)


def test_profile_prints_a_profile_as_json(tmp_path, capsys):
    assert cli.main(["profile", source(tmp_path, "a.gz")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["records"] == 1
    assert report["input"] == {"locations": 1, "lines": 3, "quads": 3, "unparsed_lines": 0}


def test_profile_writes_to_a_file_when_asked(tmp_path, capsys):
    out = tmp_path / "profile.json"
    assert cli.main(["profile", source(tmp_path, "a.gz"), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["records"] == 1
    assert capsys.readouterr().out == ""


def test_profile_honours_max_lines(tmp_path, capsys):
    assert cli.main(["profile", source(tmp_path, "a.gz"), "--max-lines", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 0


def test_export_writes_a_dataset_and_its_profile(tmp_path, capsys):
    out = tmp_path / "dataset"
    elsewhere = source(tmp_path, "b.gz", page="http://other.example.com/p/1", name="Cafe Un")
    argv = ["export", source(tmp_path, "a.gz"), elsewhere, "--out", str(out)]
    assert cli.main(argv) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["records"] == 2
    assert (out / "README.md").exists()
    assert (out / "data" / "part-00000.jsonl.gz").exists()
    assert json.loads((out / "profile.json").read_text(encoding="utf-8"))["records"] == 2


def test_export_profiles_before_deduplicating(tmp_path, capsys):
    first = source(tmp_path, "a.gz")
    second = source(tmp_path, "b.gz", page="http://example.com/p/2")
    assert cli.main(["export", first, second, "--out", str(tmp_path / "d")]) == 0
    manifest = json.loads(capsys.readouterr().out)
    profile = json.loads((tmp_path / "d" / "profile.json").read_text(encoding="utf-8"))
    assert (profile["records"], profile["duplication"]["distinct_places"]) == (2, 1)
    assert manifest["records"] == 1


def test_export_records_which_parts_it_read_in_the_card(tmp_path, capsys):
    assert (
        cli.main(["export", "--part", "7", "--out", str(tmp_path / "d"), "--max-lines", "0"]) == 0
    )
    capsys.readouterr()
    assert f"- `{part_url(7)}`" in (tmp_path / "d" / "README.md").read_text(encoding="utf-8")


def test_part_numbers_are_resolved_to_published_urls(capsys):
    assert cli.main(["profile", "--part", "3", "--max-lines", "0"]) == 0
    assert json.loads(capsys.readouterr().out)["input"]["locations"] == 1


@pytest.mark.parametrize("argv", [["profile"], ["export", "--out", "d"], ["export", "x"], []])
def test_refuses_incomplete_invocations(argv):
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 2


def test_help_documents_every_option(capsys):
    printed = ""
    for argv in (["--help"], ["profile", "--help"], ["export", "--help"], ["merge", "--help"]):
        with pytest.raises(SystemExit):
            cli.main(argv)
        printed += capsys.readouterr().out
    assert HELP_TEXTS
    for text in HELP_TEXTS:
        assert text in printed


def test_merge_folds_profiles_of_separate_parts(tmp_path, capsys):
    paths = []
    for index, name in enumerate(["Cafe Zero", "Cafe Un"]):
        assert cli.main(["profile", source(tmp_path, f"{index}.gz", name=name)]) == 0
        path = tmp_path / f"{index}.json"
        path.write_text(capsys.readouterr().out, encoding="utf-8")
        paths.append(str(path))
    assert cli.main(["merge", *paths]) == 0
    merged = json.loads(capsys.readouterr().out)
    assert merged["records"] == 2
    assert merged["input"]["lines"] == 6


def test_merge_writes_to_a_file_when_asked(tmp_path, capsys):
    assert cli.main(["profile", source(tmp_path, "a.gz"), "--out", str(tmp_path / "a.json")]) == 0
    out = tmp_path / "merged.json"
    assert cli.main(["merge", str(tmp_path / "a.json"), "--out", str(out)]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(out.read_text(encoding="utf-8"))["records"] == 1


def test_merge_needs_at_least_one_profile():
    with pytest.raises(SystemExit) as raised:
        cli.main(["merge"])
    assert raised.value.code == 2
