# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: all charms use Jubilant for integration testing."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally, find_charmcraft_paths, find_regexp_in_path


class JubilantCheck(Check):
    """Check that all charms use Jubilant for integration testing."""

    name = "jubilant"

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that all charms use Jubilant for integration testing."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        expected_conf = "import jubilant"
        found = [
            find_regexp_in_path(charm.parent / "tests" / "integration", pattern=expected_conf)
            for charm in find_charmcraft_paths(local_repo)
        ]
        if all(found):
            return {"result": CHECK_COMPLIANT, "message": "All tests use Jubilant."}
        if any(found):
            return {
                "result": CHECK_NOT_COMPLIANT,
                "message": "Some integration tests use Jubilant, but not all charms have it.",
            }
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": f"No '{expected_conf}' found in integration tests.",
        }
