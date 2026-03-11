# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has at least one topic matching each configured pattern."""

import re

from repolint.checks._base import Check, CheckResult, get_check_config
from repolint.config import CheckStatus
from repolint.utils import get_repository_topics


class GithubTopicsCheck(Check):
    """Check that the repository has topics matching all required patterns.

    Patterns are regular expressions configured under
    ``checks.github_topics.patterns`` in ``repolint.yaml``.  For each pattern,
    at least one repository topic must match.  If no patterns are configured
    the check is skipped.
    """

    name = "github_topics"
    parent = "github"
    description = (
        "Repository has all required GitHub topics. "
        "Configure patterns under 'checks.github_topics.patterns' in repolint.yaml."
    )

    def run(self, repo: str) -> CheckResult:
        """Check that every configured pattern matches at least one topic."""
        patterns: list[str] = get_check_config("github_topics").get("patterns", [])
        if not patterns:
            return CheckResult(CheckStatus.COMPLIANT, "No topic patterns configured.")

        topics = get_repository_topics(repo)
        missing = [p for p in patterns if not any(re.search(p, t) for t in topics)]
        if missing:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"No topic matches pattern(s): {', '.join(missing)}.",
            )
        return CheckResult(CheckStatus.COMPLIANT, "All required topic patterns matched.")
