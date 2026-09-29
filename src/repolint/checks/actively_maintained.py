# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository is actively maintained (no 'maintenance-mode' topic)."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import get_repository_topics


class ActivelyMaintainedCheck(Check):
    """Check that the repository is not marked as being in maintenance mode.

    Passes by default; fails only if the repository has a ``maintenance-mode``
    GitHub topic set.
    """

    name = "actively_maintained"
    parent = "_internal"
    description = "Repository is actively maintained (no 'maintenance-mode' topic)."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository does not have the 'maintenance-mode' topic."""
        topics = get_repository_topics(repo)
        if "maintenance-mode" in topics:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT, "Repository has the 'maintenance-mode' topic set."
            )
        return CheckResult(
            CheckStatus.COMPLIANT, "Repository does not have the 'maintenance-mode' topic."
        )
