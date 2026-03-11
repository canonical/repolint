# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has at least one workflow targeting Juju 4."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally, find_regexp_in_path


class Juju4Check(Check):
    """Check that the repository has at least one workflow targeting Juju 4."""

    name = "juju4"
    description = "Repository has tests for Juju 4."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has at least one workflow targeting Juju 4."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        expected_conf = "juju-channel:.*4/stable"
        if find_regexp_in_path(local_repo / ".github/workflows", expected_conf):
            return {"result": CHECK_COMPLIANT, "message": "At least one workflow uses Juju 4."}
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": f"No '{expected_conf}' found in GitHub workflow files.",
        }
