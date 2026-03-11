# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository's GitHub workflows use canonical Kubernetes."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_regexp_in_path


class Ck8sCheck(Check):
    """Check that the repository's GitHub workflows use canonical Kubernetes."""

    name = "ck8s"
    description = "Repository uses CK8s."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository's GitHub workflows use canonical Kubernetes."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return CheckResult(CheckStatus.NOT_COMPLIANT, f"Failed to clone repository: {e}")
        expected_conf = "use-canonical-k8s: true"
        if find_regexp_in_path(local_repo / ".github/workflows", expected_conf):
            return CheckResult(CheckStatus.COMPLIANT, "")
        return CheckResult(
            CheckStatus.NOT_COMPLIANT, f"No '{expected_conf}' found in GitHub workflow files."
        )
