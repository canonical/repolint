# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a squad-* GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import get_repository_topics

SQUAD_TOPICS = {"squad-apac", "squad-amer", "squad-emea"}


class SquadTopicCheck(Check):
    """Check that the repository has a squad-xxx topic."""

    name = "squad_topic"
    parent = "github"
    description = (
        "Repository has a squad-xxx topic. To fix it, add the topic via canonical-repo-automation."
    )

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has a squad-xxx topic."""
        topics = get_repository_topics(repo)
        if any(topic in SQUAD_TOPICS for topic in topics):
            return CheckResult(CheckStatus.COMPLIANT, "")
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No squad topic found.")
