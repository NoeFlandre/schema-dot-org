"""Command line entry point: profile a corpus, or export it as a dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wdcgeo.corpus import part_url
from wdcgeo.dataset import assemble, write_dataset
from wdcgeo.extract import deduplicate
from wdcgeo.pipeline import Pipeline
from wdcgeo.profile import Accumulator, merge

if TYPE_CHECKING:
    from collections.abc import Sequence

DESCRIPTION_HELP = "Mine geolocated text from Web Data Commons."
PROFILE_HELP = "Report what a corpus holds, as JSON."
EXPORT_HELP = "Write the records as a dataset, with a profile."
SOURCE_HELP = "a part file, as a path or a URL"
PART_HELP = "a part number of the published subset"
MAX_LINES_HELP = "stop after this many lines"
PROFILE_OUT_HELP = "write the profile here instead of stdout"
EXPORT_OUT_HELP = "directory to write the dataset into"
MERGE_HELP = "Fold profiles of separate parts into one."
REPORT_HELP = "a profile written by the profile command"
ASSEMBLE_HELP = "Gather the parts of a run into one dataset."
FROM_HELP = "directory holding the part_N directories"


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("sources", nargs="*", metavar="SOURCE", help=SOURCE_HELP)
    parser.add_argument("--part", type=int, action="append", metavar="N", help=PART_HELP)
    parser.add_argument("--max-lines", type=int, metavar="N", help=MAX_LINES_HELP)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wdcgeo", description=DESCRIPTION_HELP)
    commands = parser.add_subparsers(dest="command", required=True)
    profile_command = commands.add_parser("profile", help=PROFILE_HELP, description=PROFILE_HELP)
    _add_shared_arguments(profile_command)
    profile_command.add_argument("--out", type=Path, metavar="PATH", help=PROFILE_OUT_HELP)
    export_command = commands.add_parser("export", help=EXPORT_HELP, description=EXPORT_HELP)
    _add_shared_arguments(export_command)
    export_command.add_argument(
        "--out", type=Path, metavar="DIR", required=True, help=EXPORT_OUT_HELP
    )
    merge_command = commands.add_parser("merge", help=MERGE_HELP, description=MERGE_HELP)
    merge_command.add_argument("reports", nargs="+", metavar="REPORT", help=REPORT_HELP)
    merge_command.add_argument("--out", type=Path, metavar="PATH", help=PROFILE_OUT_HELP)
    assemble_command = commands.add_parser(
        "assemble", help=ASSEMBLE_HELP, description=ASSEMBLE_HELP
    )
    assemble_command.add_argument("--from", dest="parts", type=Path, required=True, help=FROM_HELP)
    assemble_command.add_argument(
        "--part", type=int, action="append", required=True, metavar="N", help=PART_HELP
    )
    assemble_command.add_argument(
        "--out", type=Path, metavar="DIR", required=True, help=EXPORT_OUT_HELP
    )
    return parser


def _report(report: dict[str, Any], out: Path | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if out is None:
        print(text)
        return
    out.write_text(text + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line, returning the process exit code."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "assemble":
        directories = [arguments.parts / f"part_{part}" for part in arguments.part]
        sources = [part_url(part) for part in arguments.part]
        _report(assemble(directories, sources, arguments.out), None)
        return 0
    if arguments.command == "merge":
        reports = [json.loads(Path(name).read_text(encoding="utf-8")) for name in arguments.reports]
        _report(merge(reports), arguments.out)
        return 0
    locations = [*arguments.sources, *(part_url(part) for part in arguments.part or ())]
    if not locations:
        parser.error(f"give at least one SOURCE or --part: {SOURCE_HELP}")
    pipeline = Pipeline(locations, max_lines=arguments.max_lines)
    if arguments.command == "profile":
        report = profile_report(pipeline)
        _report(report, arguments.out)
        return 0
    accumulator = Accumulator()
    records = deduplicate(accumulator.tap(pipeline.records()))
    manifest = write_dataset(records, arguments.out, locations)
    _report(_with_input(accumulator.to_dict(), pipeline), arguments.out / "profile.json")
    _report(manifest, arguments.out / "manifest.json")
    _report(manifest, None)
    return 0


def profile_report(pipeline: Pipeline) -> dict[str, Any]:
    """Profile everything ``pipeline`` yields, including what it read."""
    accumulator = Accumulator()
    for record in pipeline.records():
        accumulator.add(record)
    return _with_input(accumulator.to_dict(), pipeline)


def _with_input(report: dict[str, Any], pipeline: Pipeline) -> dict[str, Any]:
    return {**report, "input": pipeline.counts()}
