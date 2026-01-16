"""A tool for managing F1 data changes."""

import argparse
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, Popen

_logger = logging.getLogger(__name__)


@dataclass
class _CreateConfig:
    """Configuration for the 'create' subcommand."""

    plx_table_names: list[str]
    dest_dir: Path
    sql_filename_prefix: str
    num_of_sql_files: int = 1
    record_start: str = "----- Network"
    sql_contents_prefix: str = ""


def main(argv: list[str] | None = None) -> int:
    """Main entry point for f1dc CLI."""
    parser = argparse.ArgumentParser(
        prog="f1dc", description="A tool for managing F1 data changes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'create' subcommand
    create_parser = subparsers.add_parser("create", help="Create a new F1 data change")
    create_parser.add_argument(
        "-p",
        "--plx-table-names",
        required=True,
        help="Comma-separated list of PLX temp table names.",
    )
    create_parser.add_argument(
        "-n",
        "--num-of-sql-files",
        type=int,
        default=1,
        help="The number of SQL files to split the data change into.",
    )
    create_parser.add_argument(
        "-d",
        "--dest-dir",
        type=Path,
        required=True,
        help="The directory where generated SQL files should be stored.",
    )
    create_parser.add_argument(
        "-s",
        "--sql-filename-prefix",
        required=True,
        help="The name of the generated SQL files (will have a count appended).",
    )
    create_parser.add_argument(
        "-P",
        "--sql-contents-prefix",
        default="",
        help="This line, if provided, will be the first line of every SQL file.",
    )
    create_parser.add_argument(
        "-r",
        "--record-start",
        default="----- Network",
        help="The pattern used to identify the start of a SQL transaction.",
    )

    args = parser.parse_args(argv)

    if args.command == "create":
        cfg = _CreateConfig(
            plx_table_names=args.plx_table_names.split(","),
            dest_dir=args.dest_dir,
            sql_filename_prefix=args.sql_filename_prefix,
            num_of_sql_files=args.num_of_sql_files,
            record_start=args.record_start,
            sql_contents_prefix=args.sql_contents_prefix.replace("\\n", "\n"),
        )
        return _run_create(cfg)

    return 1


def _run_create(cfg: _CreateConfig) -> int:
    """Execute the 'create' subcommand."""
    cfg.dest_dir.mkdir(parents=True, exist_ok=True)
    tmp_sql_file = "/tmp/f1dc.sql"
    open(tmp_sql_file, "w").close()
    total_record_count = 0

    with open(tmp_sql_file, "a") as f:
        for plx_table_name in cfg.plx_table_names:
            popen = Popen(
                ["f1-sql", "--raw_output", "--server=/f1/gfp/prod"],
                stdout=PIPE,
                stdin=PIPE,
            )
            out = popen.communicate(input=f"select * from {plx_table_name};".encode())[
                0
            ]
            sql_code = (
                out.decode()
                .replace("\\n", "\n")
                .replace('"', "")
                .replace("\\'", "'")
                .replace(f"\n\n{cfg.record_start}", f"\n{cfg.record_start}")
            )
            total_record_count += sql_code.count(cfg.record_start)
            print(sql_code, file=f, end="")

    record_count = 0
    file_count = 1
    max_records_per_file = math.ceil(total_record_count / cfg.num_of_sql_files)
    _logger.info("Max SQL commands per file: %d", max_records_per_file)
    records: list[list[str]] = []

    for line in open(tmp_sql_file):
        if record_count == max_records_per_file and line.startswith(cfg.record_start):
            file_path = _get_path_from_count(cfg, file_count)
            _write_records_to_file(records, file_path, cfg.sql_contents_prefix)
            records = []
            file_count += 1
            record_count = 0
        if line.startswith(cfg.record_start):
            records.append([])
            record_count += 1
        if record_count > 0:
            records[-1].append(line)

    # Create the last SQL file.
    _write_records_to_file(
        records,
        _get_path_from_count(cfg, cfg.num_of_sql_files),
        cfg.sql_contents_prefix,
    )
    return 0


def _get_path_from_count(cfg: _CreateConfig, file_count: int) -> Path:
    """Generate output file path based on count."""
    return cfg.dest_dir / (
        os.environ["USER"]
        + "-"
        + cfg.sql_filename_prefix
        + "-"
        + str(file_count - 1)
        + ".sql"
    )


def _write_records_to_file(
    records: list[list[str]], path: Path, sql_contents_prefix: str
) -> None:
    """Write records to an SQL file."""
    _logger.info("Writing %d records to %s.", len(records), path)
    records[0][0] = records[0][0].lstrip()
    records[-1][-1] = records[-1][-1].lstrip()
    contents = "".join(["".join(r) for r in records])
    if sql_contents_prefix:
        contents = sql_contents_prefix + "\n\n" + contents
    print(contents, file=path.open("w"), end="")


if __name__ == "__main__":
    raise SystemExit(main())
