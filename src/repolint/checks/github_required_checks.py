# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has required status checks on the default branch."""

import json
import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus


def get_default_branch(repo: str) -> str:
    """Return the default branch name for the given repository."""
    cmd = [
        "gh",
        "repo",
        "view",
        repo,
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "main"


def get_required_status_checks(repo: str, branch: str) -> list[str] | None:
    """Return the list of required status check contexts for a branch, or None if unprotected."""
    owner, name = repo.split("/", 1)
    cmd = ["gh", "api", f"/repos/{owner}/{name}/branches/{branch}/protection"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    rsc = data.get("required_status_checks")
    if rsc is None:
        return None
    checks = rsc.get("checks", [])
    contexts = rsc.get("contexts", [])
    return [c["context"] for c in checks] or contexts


class GithubRequiredChecksCheck(Check):
    """Check that the default branch has required status checks configured."""

    name = "github_required_checks"
    parent = "github"
    description = (
        "Repository has required status checks on the default branch. "
        "Configure branch protection rules with at least one required status check."
    )

    def run(self, repo: str) -> CheckResult:
        """Check that the default branch has at least one required status check."""
        branch = get_default_branch(repo)
        checks = get_required_status_checks(repo, branch)
        if checks is None:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"Branch '{branch}' has no branch protection rules or required status checks.",
            )
        if not checks:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"Branch '{branch}' has branch protection but no required status checks defined.",
            )
        return CheckResult(
            CheckStatus.COMPLIANT,
            f"Branch '{branch}' has {len(checks)} required status check(s): {', '.join(checks)}.",
        )
