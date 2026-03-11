# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point for repolint."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from repolint.checks import CheckResult, configure_checks
from repolint.config import DEFAULT_CONFIG_FILE, REPORTS_PATH
from repolint.report import (
    analyze,
    render_markdown_details,
    render_markdown_overview,
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
        help=f"Path to the repolint YAML config file (default: {DEFAULT_CONFIG_FILE}).",
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
    return parser


def main() -> None:
    """Entry point for the repolint CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    config_path: Path = args.config

    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    configure_checks(config.get("checks", {}))

    try:
        repositories = resolve_repositories(config, extra_query=args.query)
    except subprocess.CalledProcessError as exc:
        parser.error(f"Failed to resolve repositories: {exc}")
        return  # unreachable; satisfies type checkers

    REPORTS_PATH.mkdir(exist_ok=True)

    json_file = REPORTS_PATH / "quality.json"
    markdown_file = REPORTS_PATH / "quality.md"

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
        details_file = REPORTS_PATH / get_repository_details_filename(repo)
        details_file.write_text(render_markdown_details(repo, repo_results))

    print(f"Reports written to {REPORTS_PATH}/")


if __name__ == "__main__":
    main()
