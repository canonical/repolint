# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: all Terraform modules use Juju provider v1."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_files_in_path, find_regexp_in_path


class TfV1Check(Check):
    """Check that all Terraform modules use Juju provider v1."""

    name = "tf_v1"
    parent = "terraform"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository uses Terraform Juju provider v1."

    def run(self, repo: str) -> CheckResult:
        """Check that all Terraform modules use Juju provider v1."""
        local_repo = clone_repository_locally(repo)
        expected_conf = r'juju\s*=\s*\{.*?\bversion\s*=\s*"~> 1\.'
        results = [
            find_regexp_in_path(tf_file.parent, expected_conf)
            for tf_file in find_files_in_path(local_repo, "versions.tf")
        ]
        if all(results):
            return CheckResult(
                CheckStatus.COMPLIANT,
                "All Terraform provider versions files use Juju provider v1.",
            )
        if any(results):
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                "Some Terraform provider versions files use Juju provider v1, but not all.",
            )
        return CheckResult(
            CheckStatus.NOT_COMPLIANT, f"No '{expected_conf}' found in the repository."
        )
