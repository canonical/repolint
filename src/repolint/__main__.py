# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point for repolint."""

import argparse
import json
import sys

from repolint.config import REPORTS_PATH, SQUADS
from repolint.report import (
    analyze,
    analyze_repo,
    render_markdown_details,
    render_markdown_overview,
)
from repolint.utils import get_repository_details_filename


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolint",
        description="Generate a repository compliance dashboard for Canonical Platform Engineering.",
    )
    parser.add_argument(
        "scope",
        metavar="scope",
        help=(
            "Scope to analyse: 'all', a squad name (americas|apac|emea), "
            "or a full repository name (e.g. canonical/my-charm)."
        ),
    )
    return parser


def main() -> None:
    """Entry point for the repolint CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    scope: str = args.scope

    # Single-repository debug mode
    if scope.startswith("canonical/") or "/" in scope:
        repo = scope
        results = analyze_repo(repo)
        print(json.dumps(results, indent=2))
        print(render_markdown_details(repo, results))
        sys.exit(0)

    valid_scopes = SQUADS | {"all"}
    if scope not in valid_scopes:
        parser.error(f"Unknown scope {scope!r}. Expected one of: {sorted(valid_scopes)}.")

    REPORTS_PATH.mkdir(exist_ok=True)

    all_results: dict = {}
    for squad in sorted(SQUADS):
        if scope != "all" and squad != scope:
            continue

        json_file = REPORTS_PATH / f"quality-{squad}.json"
        markdown_file = REPORTS_PATH / f"quality-{squad}.md"

        if json_file.exists():
            print(f"WARNING: using cached results, rm {json_file} to re-analyze.")
            with json_file.open() as fh:
                results = json.load(fh)
        else:
            results = analyze(squad)
            with json_file.open(mode="w") as fh:
                json.dump(results, fh, indent=2)

        try:
            markdown_file.write_text(render_markdown_overview(results))
        except AttributeError:
            print(
                f"Failed to render markdown table from {json_file}, consider removing the cache."
            )
            sys.exit(1)

        all_results.update(results)

    if scope == "all":
        json_file = REPORTS_PATH / "quality-all.json"
        markdown_file = REPORTS_PATH / "quality-all.md"
        with json_file.open(mode="w") as fh:
            json.dump(all_results, fh, indent=2)
        markdown_file.write_text(render_markdown_overview(all_results))
        print(f"Generated global reports in {markdown_file}.")

    for repo, repo_results in all_results.items():
        details_markdown = render_markdown_details(repo, repo_results)
        details_file = REPORTS_PATH / get_repository_details_filename(repo)
        details_file.write_text(details_markdown)


if __name__ == "__main__":
    main()
