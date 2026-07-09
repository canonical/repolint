# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository's GitHub workflows use canonical Kubernetes."""

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_files_in_path


class Ck8sCheck(Check):
    """Check that the repository's GitHub workflows use canonical Kubernetes."""

    name = "ck8s"
    parent = "integration_tests"
    depends_on = ["contains_k8s_charm", "charmci"]  # noqa: RUF012
    description = "Repository uses CK8s."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository's GitHub workflows use canonical Kubernetes."""
        local_repo = clone_repository_locally(repo)
        concierge_files = find_files_in_path(local_repo, "concierge*.yaml")
        for f in concierge_files:
            try:
                data = yaml.safe_load(f.read_text())
            except (yaml.YAMLError, UnicodeDecodeError):
                continue
            if (
                isinstance(data, dict)
                and isinstance(data.get("providers"), dict)
                and "k8s" in data["providers"]
            ):
                return CheckResult(
                    CheckStatus.COMPLIANT, "At least one concierge provisions ck8s."
                )
        return CheckResult(
            CheckStatus.NOT_COMPLIANT,
            "No 'providers.k8s' key found in any concierge*.yaml file.",
        )
