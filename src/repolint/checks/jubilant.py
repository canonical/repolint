# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: all charms use Jubilant for integration testing."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_charmcraft_paths, find_regexp_in_path


class JubilantCheck(Check):
    """Check that all charms use Jubilant for integration testing."""

    name = "jubilant"
    parent = "integration_tests"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository uses Jubilant for charm testing."

    def run(self, repo: str) -> CheckResult:
        """Check that all charms use Jubilant for integration testing."""
        local_repo = clone_repository_locally(repo)
        expected_conf = "import jubilant"
        found = [
            find_regexp_in_path(charm.parent / "tests" / "integration", pattern=expected_conf)
            for charm in find_charmcraft_paths(local_repo)
        ]
        if all(found):
            return CheckResult(CheckStatus.COMPLIANT, "All tests use Jubilant.")
        if any(found):
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                "Some integration tests use Jubilant, but not all charms have it.",
            )
        return CheckResult(
            CheckStatus.NOT_COMPLIANT, f"No '{expected_conf}' found in integration tests."
        )
