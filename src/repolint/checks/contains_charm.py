# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository contains at least one charm (charmcraft.yaml)."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally, find_charmcraft_paths


class ContainsCharmCheck(Check):
    """Check that the repository contains at least one charm."""

    name = "contains_charm"

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository contains at least one charm."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        charms = find_charmcraft_paths(local_repo)
        if charms:
            return {
                "result": CHECK_COMPLIANT,
                "message": "Charms in: " + ", ".join(str(k) for k in charms),
            }
        return {"result": CHECK_NOT_COMPLIANT, "message": "No charms found in the repository."}
