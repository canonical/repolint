# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a GitHub-to-Jira sync configuration."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally


class Github2JiraCheck(Check):
    """Check that the repository has a GitHub-to-Jira sync configuration."""

    name = "github2jira"

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has a GitHub-to-Jira sync configuration."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        integration_conf_file = local_repo / ".github/.jira_sync_config.yaml"
        if integration_conf_file.exists():
            return {"result": CHECK_COMPLIANT, "message": ""}
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": "No GitHub to Jira integration config found.",
        }
