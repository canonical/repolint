# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a squad-* GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT, SQUAD_TOPICS
from repolint.utils import get_repository_topics


class SquadTopicCheck(Check):
    """Check that the repository has a squad-xxx topic."""

    name = "squad_topic"
    description = (
        "Repository has a squad-xxx topic. To fix it, add the topic via canonical-repo-automation."
    )

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has a squad-xxx topic."""
        topics = get_repository_topics(repo)
        if any(topic in SQUAD_TOPICS for topic in topics):
            return {"result": CHECK_COMPLIANT, "message": ""}
        return {"result": CHECK_NOT_COMPLIANT, "message": "No squad topic found."}
