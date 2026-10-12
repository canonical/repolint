# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: Terraform modules comply with the CC008 Charm Terraform Standards."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally

COMPLIANCE_TOOL_SOURCE = (
    "git+https://github.com/canonical/operator-workflows"
    "@feat/terraform-full-compliance#subdirectory=terraform-compliance"
)
COMPLIANCE_TOOL_COMMAND = "terraform-check-all"
MAX_OUTPUT_CHARS = 2000


class TfCc008Check(Check):
    """Check that the repository passes the CC008 Terraform compliance tool."""

    name = "tf_cc008"
    parent = "terraform"
    depends_on = ["contains_charm", "actively_maintained"]  # noqa: RUF012
    description = "Repository Terraform modules comply with CC008."

    def run(self, repo: str) -> CheckResult:
        """Run the CC008 compliance tool and pass if its exit code is 0."""
        local_repo = clone_repository_locally(repo)
        completed = subprocess.run(
            ["uvx", "--from", COMPLIANCE_TOOL_SOURCE, COMPLIANCE_TOOL_COMMAND, "."],  # noqa: S607
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return CheckResult(CheckStatus.COMPLIANT, "terraform-check-all passed.")
        output = (completed.stdout + completed.stderr).strip()[-MAX_OUTPUT_CHARS:]
        return CheckResult(
            CheckStatus.NOT_COMPLIANT,
            f"terraform-check-all failed (exit code {completed.returncode}):\n{output}",
        )
