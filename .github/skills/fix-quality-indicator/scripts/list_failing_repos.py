#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""List repositories failing a given repolint quality indicator.

Standalone helper for the ``fix-quality-indicator`` skill. Deliberately has
no dependency on the ``repolint`` package (stdlib only) so it works even in
environments where repolint itself isn't installed — it only needs to read
the JSON report that repolint already produced.

Usage::

    list_failing_repos.py <check-name> [--report reports/quality.json]

Prints one ``org/repo`` per line for every repository whose result for
``<check-name>`` is "not compliant" (the ``NOT_COMPLIANT`` status, "❌", in
``repolint``'s ``CheckStatus`` enum). Exits with a non-zero status and a
clear error message if the report is missing or the check name is unknown.
"""

import argparse
import json
import sys
from pathlib import Path

NOT_COMPLIANT = "❌"

DEFAULT_REPORT = Path("reports/quality.json")


def _known_check_names(metadata: dict) -> set[str]:
    """Return every check name (parents and children) present in the report metadata."""
    names: set[str] = set()
    for check in metadata.get("checks", []):
        names.add(check["name"])
        for child in check.get("children", []):
            names.add(child["name"])
    return names


def list_failing_repos(check_name: str, report_path: Path) -> list[str]:
    """Return the sorted list of repos whose ``check_name`` result is NOT_COMPLIANT.

    Raises :class:`FileNotFoundError` if *report_path* doesn't exist, and
    :class:`ValueError` if *check_name* is not a known check in the report.
    """
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    with report_path.open() as fh:
        data = json.load(fh)

    known_checks = _known_check_names(data.get("metadata", {}))
    if known_checks and check_name not in known_checks:
        raise ValueError(
            f"Unknown check {check_name!r}. Known checks: {', '.join(sorted(known_checks))}"
        )

    failing = []
    for repo, results in data.get("results", {}).items():
        result = results.get(check_name)
        if result is not None and result.get("result") == NOT_COMPLIANT:
            failing.append(repo)
    return sorted(failing)


def main() -> None:
    """Parse CLI arguments and print the failing repositories, one per line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check_name", help="Name of the repolint check/quality indicator.")
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"Path to the quality.json report (default: {DEFAULT_REPORT}).",
    )
    args = parser.parse_args()

    try:
        failing_repos = list_failing_repos(args.check_name, args.report)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for repo in failing_repos:
        print(repo)


if __name__ == "__main__":
    main()
