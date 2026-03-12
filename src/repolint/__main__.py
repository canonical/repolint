# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point for repolint."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from repolint.checks import CheckResult, configure_checks
from repolint.config import DEFAULT_CONFIG_FILE, DEFAULT_REPORTS_DIR
from repolint.report import (
    analyze,
    render_markdown_details,
    render_markdown_overview,
    render_report_in_terminal,
)
from repolint.utils import get_repository_details_filename, load_config, resolve_repositories


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolint",
        description="Generate a repository compliance dashboard for Canonical Platform Engineering.",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        type=Path,
        default=DEFAULT_CONFIG_FILE,
        help=(
            f"Path to the repolint YAML config file (default: {DEFAULT_CONFIG_FILE}). "
            "Optional when --query is provided."
        ),
    )
    parser.add_argument(
        "--query",
        metavar="QUERY",
        default=None,
        help=(
            "GitHub repository search query whose results are merged with the "
            "repositories from the config file. Archived repositories are automatically "
            "excluded. Example: 'org:canonical topic:platform-engineering topic:squad-emea'."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help=f"Directory where reports are written (default: {DEFAULT_REPORTS_DIR}).",
    )
    parser.add_argument(
        "--output",
        metavar="NAME",
        default="quality",
        help=(
            "Base name for the report files (default: quality). "
            "Produces NAME.json, NAME.md, and NAME-<repo>-details.md."
        ),
    )
    parser.add_argument(
        "--show-report",
        metavar="FILE",
        nargs="?",
        const="",
        default=None,
        help=(
            "Render a Markdown report in the terminal. "
            "Optionally accepts a path to a specific report file. "
            "When no file is given the default overview report "
            "(<output-dir>/<output>.md) is shown. "
            "Skips repository analysis."
        ),
    )
    return parser


def main() -> None:
    """Entry point for the repolint CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.show_report is not None:
        report_path = (
            Path(args.show_report) if args.show_report else args.output_dir / f"{args.output}.md"
        )
        if not report_path.exists():
            parser.error(f"Report file not found: {report_path}")
        render_report_in_terminal(report_path.read_text())
        return

    config_path: Path = args.config

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        if args.query is None:
            parser.error(str(exc))
        config = {}
    except ValueError as exc:
        parser.error(str(exc))

    reports_dir: Path = args.output_dir

    configure_checks(config.get("checks", {}))

    try:
        repositories = resolve_repositories(config, extra_query=args.query)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no output)"
        parser.error(f"Repository query failed: {stderr}")
        return  # unreachable; satisfies type checkers

    reports_dir.mkdir(parents=True, exist_ok=True)

    json_file = reports_dir / f"{args.output}.json"
    markdown_file = reports_dir / f"{args.output}.md"

    if json_file.exists():
        print(f"WARNING: using cached results, rm {json_file} to re-analyze.")
        with json_file.open() as fh:
            raw = json.load(fh)
        results = {
            repo: {k: CheckResult.from_dict(v) for k, v in repo_results.items()}
            for repo, repo_results in raw.items()
        }
    else:
        results = analyze(repositories)
        with json_file.open(mode="w") as fh:
            json.dump(
                {
                    repo: {k: v.to_dict() for k, v in repo_results.items()}
                    for repo, repo_results in results.items()
                },
                fh,
                indent=2,
            )

    try:
        markdown_file.write_text(render_markdown_overview(results))
    except AttributeError:
        print(f"Failed to render markdown table from {json_file}, consider removing the cache.")
        sys.exit(1)

    for repo, repo_results in results.items():
        details_file = reports_dir / get_repository_details_filename(repo)
        details_file.write_text(render_markdown_details(repo, repo_results))

    print(f"Reports written to {reports_dir}/")


if __name__ == "__main__":
    main()
