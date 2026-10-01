# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository contains at least one rock (rockcraft.yaml)."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_rockcraft_paths


class ContainsRockCheck(Check):
    """Check that the repository contains at least one rock."""

    name = "contains_rock"
    parent = "_internal"
    description = "Repository contains at least one rock (rockcraft.yaml file)."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository contains at least one rock."""
        local_repo = clone_repository_locally(repo)
        rocks = find_rockcraft_paths(local_repo)
        if rocks:
            return CheckResult(
                CheckStatus.COMPLIANT, "Rocks in: " + ", ".join(str(k) for k in rocks)
            )
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No rocks found in the repository.")
