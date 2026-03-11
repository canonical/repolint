# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository uses ops.testing instead of the old Harness."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_regexp_in_path


class OpsTestingCheck(Check):
    """Check that the repository uses ops.testing instead of the old Harness."""

    name = "ops_testing"
    depends_on = ["contains_charm"]  # noqa: RUF012
    hidden = True
    description = "Repository doesn't use harness."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository uses ops.testing instead of the old Harness."""
        local_repo = clone_repository_locally(repo)
        if find_regexp_in_path(local_repo, pattern="harness", recursive=True):
            return CheckResult(CheckStatus.NOT_COMPLIANT, "Found references to harness.")
        return CheckResult(CheckStatus.COMPLIANT, "No reference to harness found.")
