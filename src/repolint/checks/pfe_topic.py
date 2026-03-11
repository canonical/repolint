# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has the 'platform-engineering' GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import get_repository_topics


class PfeTopicCheck(Check):
    """Check that the repository has the 'platform-engineering' topic."""

    name = "pfe_topic"
    description = "Repository has a platform-engineering topic. To fix it, add the topic via canonical-repo-automation."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has the 'platform-engineering' topic."""
        topics = get_repository_topics(repo)
        if "platform-engineering" in topics:
            return {"result": CHECK_COMPLIANT, "message": ""}
        return {"result": CHECK_NOT_COMPLIANT, "message": "No platform-engineering topic found."}
