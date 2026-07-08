# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point for repolint."""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NamedTuple

from repolint.catalog import load_catalog
from repolint.checks import build_checks_metadata, configure_checks, list_checks
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


def _get_version() -> str:
    try:
        return version("repolint")
    except PackageNotFoundError:
        return "unknown"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolint",
        description="Generate a repository compliance dashboard for Canonical Platform Engineering.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
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
        "--catalog",
        metavar="FILE",
        type=Path,
        default=None,
        help=(
            "Path to the product catalog JSON file produced by scripts/fetch_catalog.py "
            "(default: catalog.json next to the config file). "
            "When absent, the overview report uses a flat layout with no tier grouping."
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


def _read_cache(json_file: Path) -> tuple[dict, str | None]:
    """Return ``(results, generated_at)`` from a cache file, or ``({}, None)``.

    Handles both the current wrapped format (``{"metadata": …, "results": …}``)
    and the legacy flat format (a bare ``repo -> results`` mapping).
    """
    if not json_file.exists():
        return {}, None
    with json_file.open() as fh:
        raw = json.load(fh)
    if "results" in raw:
        return raw["results"], raw.get("metadata", {}).get("generated_at")
    # Legacy flat format — no metadata wrapper.
    return raw, None


def _load_quality_data(json_file: Path, repositories: list[str]) -> dict:
    """Return the quality data dict for *repositories*, reusing cache where valid.

    Cached repository results are reused only when they cover every currently
    registered check; repositories that are missing from the cache (or missing a
    newly added check) are analysed afresh. Repositories no longer requested are
    dropped so the report always matches the requested set.
    """
    cached_results, cached_generated_at = _read_cache(json_file)
    registered_checks = {check.name for check in list_checks()}

    results: dict[str, dict] = {}
    to_analyze: list[str] = []
    for repo in repositories:
        cached_entry = cached_results.get(repo)
        if cached_entry is not None and registered_checks.issubset(cached_entry.keys()):
            results[repo] = cached_entry
        else:
            to_analyze.append(repo)

    reused = len(results)
    if reused and to_analyze:
        print(f"Reusing cached results for {reused} repository(ies); analyzing {len(to_analyze)}.")
    elif reused:
        print(
            f"Reusing cached results for all {reused} repository(ies) (use --no-cache to refresh)."
        )

    if to_analyze:
        fresh = analyze(to_analyze)
        for repo, repo_results in fresh.items():
            results[repo] = {name: result.to_dict() for name, result in repo_results.items()}

    # Preserve the original timestamp when nothing was re-analyzed.
    generated_at = (
        cached_generated_at
        if cached_generated_at and not to_analyze
        else datetime.now().isoformat()
    )
    quality_data = {
        "metadata": {
            "schema": "v0",
            "generated_at": generated_at,
            "checks": build_checks_metadata(),
        },
        "results": {repo: results[repo] for repo in sorted(repositories)},
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


class RepoSelection(NamedTuple):
    """Outcome of applying the REPO / CWD shortcuts.

    ``cwd_repo`` is set only when CWD shortcut mode is active (no explicit repo,
    query, or config — the repository was auto-detected from the git remote of
    the current directory). It is ``None`` for standard mode.
    """

    cwd_repo: str | None


def _apply_repo_shortcuts(
    args: argparse.Namespace, config: dict, parser: argparse.ArgumentParser
) -> RepoSelection:
    """Apply the positional REPO shortcut or CWD auto-detection to *config* in place.

    Returns a :class:`RepoSelection` whose ``cwd_repo`` is the auto-detected
    repository name when CWD shortcut mode is activated, and ``None`` otherwise.
    """
    if args.repo is not None:
        config.setdefault("repositories", [])
        if args.repo not in config["repositories"]:
            config["repositories"].insert(0, args.repo)
        return RepoSelection(cwd_repo=None)

    if args.query is not None or config.get("repositories") or config.get("repository_query"):
        return RepoSelection(cwd_repo=None)

    detected = get_current_repo()
    if detected:
        print(f"Auto-detected repository from current directory: {detected}")
        config["repositories"] = [detected]
        return RepoSelection(cwd_repo=detected)
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
    selection = _apply_repo_shortcuts(args, config, parser)

    try:
        repositories = resolve_repositories(config, extra_query=args.query)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no output)"
        parser.error(f"Repository query failed: {stderr}")
        return  # unreachable; satisfies type checkers

    if selection.cwd_repo is not None:
        _run_shortcut_mode(args, selection.cwd_repo, repositories)
    else:
        _run_standard_mode(args, repositories)


def _resolve_catalog_path(args: argparse.Namespace) -> Path:
    """Return the catalog file path from CLI args or the default beside the config."""
    if args.catalog is not None:
        return args.catalog
    return args.config.parent / "catalog.json"


def _run_standard_mode(args: argparse.Namespace, repositories: list[str]) -> None:
    """Run analysis and write reports to the configured output directory."""
    reports_dir: Path = args.output_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_file = reports_dir / f"{args.output}.json"

    if args.no_cache and json_file.exists():
        json_file.unlink()
        print(f"Cache cleared: {json_file}")

    quality_data = _load_quality_data(json_file, repositories)
    service_levels = load_catalog(_resolve_catalog_path(args))
    _write_reports(reports_dir, args.output, quality_data, service_levels)

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
        service_levels = load_catalog(_resolve_catalog_path(args))
        _write_reports(tmp_dir, args.output, quality_data, service_levels)
        details_file = tmp_dir / get_repository_details_filename(shortcut_repo)
        render_report_in_terminal(details_file.read_text())


def _write_reports(
    reports_dir: Path,
    output: str,
    quality_data: dict,
    service_levels: dict[str, str] | None = None,
) -> None:
    """Write all Markdown report files to *reports_dir*."""
    markdown_file = reports_dir / f"{output}.md"
    json_file = reports_dir / f"{output}.json"

    try:
        markdown_file.write_text(
            render_markdown_overview(quality_data, output=output, service_levels=service_levels)
        )
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
