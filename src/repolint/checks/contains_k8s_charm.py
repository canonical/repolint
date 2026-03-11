# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository contains at least one Kubernetes charm."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_charmcraft_paths


class ContainsK8sCharmCheck(Check):
    """Check that the repository contains at least one Kubernetes charm."""

    name = "contains_k8s_charm"
    parent = "_internal"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository contains at least one Kubernetes charm."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository contains at least one Kubernetes charm."""
        local_repo = clone_repository_locally(repo)
        charms = find_charmcraft_paths(local_repo)
        k8s_charms = [charm for charm in charms if "k8s-api" in charm.read_text()]
        if k8s_charms:
            return CheckResult(
                CheckStatus.COMPLIANT,
                "Kubernetes charms in: " + ", ".join(str(k) for k in k8s_charms),
            )
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No k8s charms found in the repository.")
