# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository contains at least one charm (charmcraft.yaml)."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_charmcraft_paths


class ContainsCharmCheck(Check):
    """Check that the repository contains at least one charm."""

    name = "contains_charm"
    description = "Repository contains at least one charm (charmcraft.yaml file)."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository contains at least one charm."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return CheckResult(CheckStatus.NOT_COMPLIANT, f"Failed to clone repository: {e}")
        charms = find_charmcraft_paths(local_repo)
        if charms:
            return CheckResult(
                CheckStatus.COMPLIANT, "Charms in: " + ", ".join(str(k) for k in charms)
            )
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No charms found in the repository.")
