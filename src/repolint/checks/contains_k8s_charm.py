# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository contains at least one Kubernetes charm."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally, find_charmcraft_paths


class ContainsK8sCharmCheck(Check):
    """Check that the repository contains at least one Kubernetes charm."""

    name = "contains_k8s_charm"
    description = "Repository contains at least one Kubernetes charm."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository contains at least one Kubernetes charm."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        charms = find_charmcraft_paths(local_repo)
        k8s_charms = [charm for charm in charms if "k8s-api" in charm.read_text()]
        if k8s_charms:
            return {
                "result": CHECK_COMPLIANT,
                "message": "Kubernetes charms in: " + ", ".join(str(k) for k in k8s_charms),
            }
        return {"result": CHECK_NOT_COMPLIANT, "message": "No k8s charms found in the repository."}
