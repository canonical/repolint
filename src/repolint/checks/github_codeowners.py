# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a CODEOWNERS file matching expected content patterns."""

import re
from pathlib import Path

from repolint.checks._base import Check, CheckResult, get_check_config
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally

# Locations GitHub recognizes for a CODEOWNERS file, checked in this order.
CODEOWNERS_LOCATIONS = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]


def find_codeowners_file(repo_path: Path) -> Path | None:
    """Return the first existing CODEOWNERS file under *repo_path*, or None."""
    for location in CODEOWNERS_LOCATIONS:
        candidate = repo_path / location
        if candidate.is_file():
            return candidate
    return None


def _content_lines(path: Path) -> list[str]:
    """Return non-empty, non-comment lines from a CODEOWNERS file."""
    lines = path.read_text().splitlines()
    return [line for line in (line.strip() for line in lines) if line and not line.startswith("#")]


class GithubCodeownersCheck(Check):
    """Check that the repository has a CODEOWNERS file matching expected patterns.

    Configured under ``checks.codeowners`` in ``repolint.yaml``:

    - ``excluded``: list of ``org/repo`` strings to skip (standard mechanism).
    - ``valid_patterns``: list of regexes; at least one must match at least
      one non-empty, non-comment line of the CODEOWNERS file.
    - ``invalid_patterns``: list of regexes; none may match any non-empty,
      non-comment line of the CODEOWNERS file.

    If no CODEOWNERS file is found (checked at ``CODEOWNERS``,
    ``.github/CODEOWNERS`` and ``docs/CODEOWNERS``), the check is
    not compliant.
    """

    name = "codeowners"
    parent = "github"
    description = (
        "Repository has a CODEOWNERS file matching expected patterns. "
        "Configure 'checks.codeowners.valid_patterns' and "
        "'checks.codeowners.invalid_patterns' in repolint.yaml."
    )

    def run(self, repo: str) -> CheckResult:
        """Check that CODEOWNERS exists and matches the configured patterns."""
        repo_path = clone_repository_locally(repo)
        codeowners_path = find_codeowners_file(repo_path)
        if codeowners_path is None:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"No CODEOWNERS file found (checked {', '.join(CODEOWNERS_LOCATIONS)}).",
            )

        lines = _content_lines(codeowners_path)
        config = get_check_config("codeowners")
        valid_patterns: list[str] = config.get("valid_patterns", [])
        invalid_patterns: list[str] = config.get("invalid_patterns", [])

        missing_valid = valid_patterns and not any(
            re.search(p, line) for p in valid_patterns for line in lines
        )
        matched_invalid = [
            p for p in invalid_patterns if any(re.search(p, line) for line in lines)
        ]

        if missing_valid or matched_invalid:
            problems = []
            if missing_valid:
                problems.append(
                    f"no line matches any of the required pattern(s): {', '.join(valid_patterns)}"
                )
            if matched_invalid:
                problems.append(
                    f"a line matches disallowed pattern(s): {', '.join(matched_invalid)}"
                )
            return CheckResult(CheckStatus.NOT_COMPLIANT, "; ".join(problems) + ".")

        return CheckResult(
            CheckStatus.COMPLIANT, "CODEOWNERS file present and matches all patterns."
        )
