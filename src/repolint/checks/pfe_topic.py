# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has the 'platform-engineering' GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import get_repository_topics


class PfeTopicCheck(Check):
    """Check that the repository has the 'platform-engineering' topic."""

    name = "pfe_topic"
    description = "Repository has a platform-engineering topic. To fix it, add the topic via canonical-repo-automation."
    hidden = True

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has the 'platform-engineering' topic."""
        topics = get_repository_topics(repo)
        if "platform-engineering" in topics:
            return CheckResult(CheckStatus.COMPLIANT, "")
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No platform-engineering topic found.")
