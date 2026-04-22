# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point for repolint."""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from repolint.checks import build_checks_metadata, configure_checks
from repolint.config import DEFAULT_CONFIG_FILE, DEFAULT_REPORTS_DIR
from repolint.report import (
    analyze,
    render_markdown_details,
    render_markdown_overview,
    render_markdown_parent_check,
    render_markdown_subcheck,
    render_report_in_terminal,
)
from repolint.utils import (
    get_current_repo,
    get_git_toplevel,
    get_repository_details_filename,
    load_config,
    local_repo_override,
    resolve_repositories,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolint",
        description="Generate a repository compliance dashboard for Canonical Platform Engineering.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('repolint')}",
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
        "--no-cache",
        action="store_true",
        default=False,
        help="Delete the cached JSON report and re-run the analysis.",
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
    parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        metavar="REPO",
        help=(
            "GitHub repository full name (e.g. canonical/my-repo). "
            "Shorthand for adding the repository to the analysis list. "
            "Cannot be combined with --query."
        ),
    )
    return parser


def _load_quality_data(json_file: Path, repositories: list[str]) -> dict:
    """Return the quality data dict, loading from cache or running analysis."""
    if json_file.exists():
        print(f"WARNING: using cached results, rm {json_file} to re-analyze.")
        with json_file.open() as fh:
            raw = json.load(fh)
        if "results" in raw:
            return raw
        # Legacy format (flat dict without metadata wrapper) — reconstruct.
        return {
            "metadata": {"schema": "v0", "generated_at": None, "checks": build_checks_metadata()},
            "results": raw,
        }

    results = analyze(repositories)
    quality_data = {
        "metadata": {
            "schema": "v0",
            "generated_at": datetime.now().isoformat(),
            "checks": build_checks_metadata(),
        },
        "results": {
            repo: {k: v.to_dict() for k, v in repo_results.items()}
            for repo, repo_results in results.items()
        },
    }
    with json_file.open(mode="w") as fh:
        json.dump(quality_data, fh, indent=2)
    return quality_data


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Validate mutually exclusive argument combinations early."""
    if args.show_report is not None and args.repo is not None:
        parser.error("Cannot combine positional REPO with --show-report.")
    if args.repo is not None and args.query is not None:
        parser.error("Cannot combine positional REPO with --query.")
    if args.repo is not None:
        parts = args.repo.split("/")
        if len(parts) != 2 or not all(parts):
            parser.error(f"Invalid repository name '{args.repo}'. Expected 'owner/repo' format.")


def _apply_repo_shortcuts(
    args: argparse.Namespace, config: dict, parser: argparse.ArgumentParser
) -> str | None:
    """Apply the positional REPO shortcut or CWD auto-detection to *config* in place.

    Returns the auto-detected repository name when CWD shortcut mode is
    activated, or *None* in all other cases.
    """
    if args.repo is not None:
        config.setdefault("repositories", [])
        if args.repo not in config["repositories"]:
            config["repositories"].insert(0, args.repo)
        return None

    if args.query is not None or config.get("repositories") or config.get("repository_query"):
        return None

    detected = get_current_repo()
    if detected:
        print(f"Auto-detected repository from current directory: {detected}")
        config["repositories"] = [detected]
        return detected
    else:
        parser.error(
            "No repositories to analyze. Provide a REPO argument, use --query, "
            "create a repolint.yaml, or run from a directory with a GitHub remote."
        )


def main() -> None:
    """Entry point for the repolint CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    _validate_args(args, parser)

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
        if config_path != DEFAULT_CONFIG_FILE:
            # User explicitly provided a config path — don't silently ignore missing file.
            parser.error(str(exc))
        config = {}
    except ValueError as exc:
        parser.error(str(exc))

    configure_checks(config.get("checks", {}))

    # Apply shortcuts: positional REPO arg or CWD auto-detection.
    # Returns the detected repo name when CWD shortcut mode is active.
    shortcut_repo = _apply_repo_shortcuts(args, config, parser)

    try:
        repositories = resolve_repositories(config, extra_query=args.query)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no output)"
        parser.error(f"Repository query failed: {stderr}")
        return  # unreachable; satisfies type checkers

    if shortcut_repo:
        _run_shortcut_mode(args, shortcut_repo, repositories)
    else:
        _run_standard_mode(args, repositories)


def _run_standard_mode(args: argparse.Namespace, repositories: list[str]) -> None:
    """Run analysis and write reports to the configured output directory."""
    reports_dir: Path = args.output_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_file = reports_dir / f"{args.output}.json"

    if args.no_cache and json_file.exists():
        json_file.unlink()
        print(f"Cache cleared: {json_file}")

    quality_data = _load_quality_data(json_file, repositories)
    _write_reports(reports_dir, args.output, quality_data)

    print(f"Reports written to {reports_dir}/")


def _run_shortcut_mode(
    args: argparse.Namespace, shortcut_repo: str, repositories: list[str]
) -> None:
    """Run analysis in CWD shortcut mode.

    Uses the current git repository root as the local clone (no network clone
    needed), writes reports to a temporary directory, and immediately renders
    the per-repository detail report in the terminal.
    """
    repo_root = get_git_toplevel() or Path.cwd()

    with (
        local_repo_override(shortcut_repo, repo_root),
        tempfile.TemporaryDirectory(prefix="repolint-") as tmp_str,
    ):
        tmp_dir = Path(tmp_str)
        json_file = tmp_dir / f"{args.output}.json"
        quality_data = _load_quality_data(json_file, repositories)
        _write_reports(tmp_dir, args.output, quality_data)
        details_file = tmp_dir / get_repository_details_filename(shortcut_repo)
        render_report_in_terminal(details_file.read_text())


def _write_reports(reports_dir: Path, output: str, quality_data: dict) -> None:
    """Write all Markdown report files to *reports_dir*."""
    markdown_file = reports_dir / f"{output}.md"
    json_file = reports_dir / f"{output}.json"

    try:
        markdown_file.write_text(render_markdown_overview(quality_data, output=output))
    except AttributeError:
        print(f"Failed to render markdown table from {json_file}, consider removing the cache.")
        sys.exit(1)

    for repo in quality_data["results"]:
        details_file = reports_dir / get_repository_details_filename(repo)
        details_file.write_text(render_markdown_details(repo, quality_data))

    for check_group in quality_data["metadata"]["checks"]:
        if check_group["description"] is None:
            continue  # skip unregistered helper groups (e.g. _internal)
        parent_name = check_group["name"]
        parent_desc = check_group["description"] or ""
        children = check_group["children"]
        parent_file = reports_dir / f"{output}-{parent_name}.md"
        parent_file.write_text(
            render_markdown_parent_check(parent_name, parent_desc, children, quality_data, output)
        )

    for check_group in quality_data["metadata"]["checks"]:
        for child in check_group["children"]:
            subcheck_name = child["name"]
            subcheck_desc = child.get("description") or ""
            subcheck_file = reports_dir / f"{output}-{subcheck_name}.md"
            subcheck_file.write_text(
                render_markdown_subcheck(subcheck_name, subcheck_desc, quality_data)
            )


if __name__ == "__main__":
    main()
