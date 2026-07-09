# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has at least one workflow targeting Juju 4."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_regexp_in_path


class Juju4Check(Check):
    """Check that the repository has at least one workflow targeting Juju 4."""

    name = "juju4"
    parent = "integration_tests"
    depends_on = ["contains_charm", "charmci"]  # noqa: RUF012
    description = "Repository has tests for Juju 4."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository has at least one workflow targeting Juju 4."""
        local_repo = clone_repository_locally(repo)
        expected_conf = "juju4"
        if find_regexp_in_path(local_repo / "spread.yaml", expected_conf):
            return CheckResult(CheckStatus.COMPLIANT, "At least one test uses Juju 4.")
        return CheckResult(CheckStatus.NOT_COMPLIANT, f"No '{expected_conf}' spread.yaml.")
