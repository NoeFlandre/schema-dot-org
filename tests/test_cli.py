import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import wdcgeo
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


def test_export_leaves_its_manifest_in_the_dataset_directory(tmp_path, capsys):
    out = tmp_path / "part_0"
    assert cli.main(["export", source(tmp_path, "a.gz"), "--out", str(out)]) == 0
    capsys.readouterr()
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["records"] == 1


def test_assemble_builds_one_dataset_from_the_parts_of_a_run(tmp_path, capsys):
    parts = tmp_path / "parts"
    for index, page in enumerate(["http://a.example.com/1", "http://b.example.com/1"]):
        argv = [
            "export",
            source(tmp_path, f"{index}.gz", page=page),
            "--out",
            str(parts / f"part_{index * 7}"),
        ]
        assert cli.main(argv) == 0
    capsys.readouterr()

    argv = [
        "assemble",
        "--from",
        str(parts),
        "--part",
        "0",
        "--part",
        "7",
        "--out",
        str(tmp_path / "d"),
    ]
    assert cli.main(argv) == 0

    manifest = json.loads(capsys.readouterr().out)
    assert manifest["parts"] == 2
    assert manifest["records"] == 2
    dataset = tmp_path / "d"
    assert sorted(path.name for path in (dataset / "data").iterdir()) == manifest["shards"]
    assert json.loads((dataset / "profile.json").read_text(encoding="utf-8"))["records"] == 2
    card = (dataset / "README.md").read_text(encoding="utf-8")
    assert f"- `{part_url(0)}`" in card
    assert f"- `{part_url(7)}`" in card


def test_part_numbers_are_read_as_numbers_not_as_text(tmp_path, capsys):
    out = tmp_path / "d"
    assert cli.main(["export", "--part", "007", "--max-lines", "0", "--out", str(out)]) == 0
    capsys.readouterr()
    assert f"- `{part_url(7)}`" in (out / "README.md").read_text(encoding="utf-8")


def test_assemble_reads_part_numbers_as_numbers(tmp_path, capsys):
    parts = tmp_path / "parts"
    assert cli.main(["export", source(tmp_path, "a.gz"), "--out", str(parts / "part_7")]) == 0
    capsys.readouterr()
    argv = ["assemble", "--from", str(parts), "--part", "007", "--out", str(tmp_path / "d")]
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 1


def test_json_output_is_indented_for_a_human_to_read(tmp_path, capsys):
    assert cli.main(["export", source(tmp_path, "a.gz"), "--out", str(tmp_path / "d")]) == 0
    assert capsys.readouterr().out == (
        "{\n"
        '  "records": 1,\n'
        '  "shards": [\n'
        '    "part-00000.jsonl.gz"\n'
        "  ],\n"
        '  "card": "README.md"\n'
        "}\n"
    )


def test_output_leaves_text_outside_ascii_as_it_is(tmp_path, capsys):
    page = "http://café.example.com/p/1"
    assert cli.main(["profile", source(tmp_path, "a.gz", page=page)]) == 0
    assert "café.example.com" in capsys.readouterr().out


def test_error_says_what_is_missing(capsys):
    with pytest.raises(SystemExit):
        cli.main(["profile"])
    assert "give at least one SOURCE or --part" in capsys.readouterr().err


def test_assemble_shows_the_map_in_the_card_when_asked(tmp_path, capsys):
    parts = tmp_path / "parts"
    assert cli.main(["export", source(tmp_path, "a.gz"), "--out", str(parts / "part_0")]) == 0
    capsys.readouterr()
    out = tmp_path / "d"
    argv = ["assemble", "--from", str(parts), "--part", "0", "--out", str(out), "--map", "map.png"]
    assert cli.main(argv) == 0
    capsys.readouterr()
    assert "![Density of the records over the world](map.png)" in (out / "README.md").read_text(
        encoding="utf-8"
    )


# Golden help text: argparse metavars, program name and layout are part of the
# published interface, and nothing else pins them down.
HELP = {
    "wdcgeo": """\
usage: wdcgeo [-h] {profile,export,merge,assemble} ...

Mine geolocated text from Web Data Commons.

positional arguments:
  {profile,export,merge,assemble}
    profile             Report what a corpus holds, as JSON.
    export              Write the records as a dataset, with a profile.
    merge               Fold profiles of separate parts into one.
    assemble            Gather the parts of a run into one dataset.

options:
  -h, --help            show this help message and exit
""",
    "profile": """\
usage: wdcgeo profile [-h] [--part N] [--max-lines N] [--out PATH]
                      [SOURCE ...]

Report what a corpus holds, as JSON.

positional arguments:
  SOURCE         a part file, as a path or a URL

options:
  -h, --help     show this help message and exit
  --part N       a part number of the published subset
  --max-lines N  stop after this many lines
  --out PATH     write the profile here instead of stdout
""",
    "export": """\
usage: wdcgeo export [-h] [--part N] [--max-lines N] --out DIR [SOURCE ...]

Write the records as a dataset, with a profile.

positional arguments:
  SOURCE         a part file, as a path or a URL

options:
  -h, --help     show this help message and exit
  --part N       a part number of the published subset
  --max-lines N  stop after this many lines
  --out DIR      directory to write the dataset into
""",
    "merge": """\
usage: wdcgeo merge [-h] [--out PATH] REPORT [REPORT ...]

Fold profiles of separate parts into one.

positional arguments:
  REPORT      a profile written by the profile command

options:
  -h, --help  show this help message and exit
  --out PATH  write the profile here instead of stdout
""",
    "assemble": """\
usage: wdcgeo assemble [-h] --from DIR --part N --out DIR [--map NAME]

Gather the parts of a run into one dataset.

options:
  -h, --help  show this help message and exit
  --from DIR  directory holding the part_N directories
  --part N    a part number of the published subset
  --out DIR   directory to write the dataset into
  --map NAME  image to show in the card, e.g. map.png
""",
}


@pytest.mark.parametrize("command", list(HELP))
def test_help_is_exactly_as_published(command, capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    argv = ["--help"] if command == "wdcgeo" else [command, "--help"]
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 0
    assert capsys.readouterr().out == HELP[command]


def test_every_help_string_reaches_the_help_output():
    printed = "".join(HELP.values())
    assert HELP_TEXTS
    for text in HELP_TEXTS:
        assert text in printed


def test_reads_and_writes_utf8_whatever_the_locale(tmp_path):
    """A run under an ASCII locale must still read and write UTF-8.

    Every encoding in this package is passed explicitly for this reason. Left
    to the locale, the same run raises `UnicodeDecodeError` on the corpus or
    writes mojibake into the dataset, and nothing in a UTF-8 development
    environment would ever say so.
    """
    name = "Café Zéro"
    argv = ["export", source(tmp_path, "a.gz", name=name), "--out", str(tmp_path / "d")]
    package_root = Path(wdcgeo.__file__).parent.parent
    # The parent environment carries through so that the subprocess runs the
    # same code as this process, mutation harness included; only the locale and
    # the import path are forced.
    environment = {
        **os.environ,
        "PYTHONPATH": str(package_root),
        "LC_ALL": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
    }
    program = "import sys; from wdcgeo.cli import main; sys.exit(main())"

    finished = subprocess.run(
        [sys.executable, "-c", program, *argv], capture_output=True, env=environment, check=False
    )

    assert finished.returncode == 0, finished.stderr.decode("utf-8", "replace")
    assert json.loads(finished.stdout.decode("utf-8"))["records"] == 1
    with gzip.open(tmp_path / "d" / "data" / "part-00000.jsonl.gz", "rt", encoding="utf-8") as h:
        assert json.loads(h.read())["name"] == name


def test_reads_nothing_at_all_when_the_cap_is_zero(tmp_path, capsys):
    absent = str(tmp_path / "absent.gz")
    assert cli.main(["profile", absent, "--max-lines", "0"]) == 0
    assert json.loads(capsys.readouterr().out)["input"]["lines"] == 0
