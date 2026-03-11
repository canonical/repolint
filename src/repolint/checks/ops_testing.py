# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository uses ops.testing instead of the old Harness."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_regexp_in_path


class OpsTestingCheck(Check):
    """Check that the repository uses ops.testing instead of the old Harness."""

    name = "ops_testing"
    description = "Repository doesn't use harness."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository uses ops.testing instead of the old Harness."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return CheckResult(CheckStatus.NOT_COMPLIANT, f"Failed to clone repository: {e}")
        if find_regexp_in_path(local_repo, pattern="harness", recursive=True):
            return CheckResult(CheckStatus.NOT_COMPLIANT, "Found references to harness.")
        return CheckResult(CheckStatus.COMPLIANT, "No reference to harness found.")
