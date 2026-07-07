# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: unit test workflows use GitHub-hosted runners, not self-hosted runners."""

from pathlib import Path
from typing import Any

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally

_OPERATOR_WORKFLOWS_PATTERN = "uses: canonical/operator-workflows/.github/workflows/test.yaml"


def _find_self_hosted_runner(data: Any) -> bool:
    """Recursively return True if any 'self-hosted-runner' key has value True."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "self-hosted-runner" and value is True:
                return True
            if _find_self_hosted_runner(value):
                return True
    elif isinstance(data, list):
        for item in data:
            if _find_self_hosted_runner(item):
                return True
    return False


def _workflow_files(repo_path: Path) -> list[Path]:
    """Return all YAML files under .github/workflows/."""
    workflows_dir = repo_path / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []
    return [f for f in workflows_dir.iterdir() if f.is_file() and f.suffix in {".yaml", ".yml"}]


class UseGhRunnersCheck(Check):
    """Check that operator-workflows test jobs use GitHub-hosted runners."""

    name = "use_gh_runners"
    parent = "unit_tests"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository uses GitHub-hosted runners for unit tests."

    def run(self, repo: str) -> CheckResult:
        """Check that no workflow using operator-workflows test.yaml enables self-hosted runners."""
        local_repo = clone_repository_locally(repo)

        matching_files = [
            f
            for f in _workflow_files(local_repo)
            if _OPERATOR_WORKFLOWS_PATTERN in f.read_text(encoding="utf-8", errors="ignore")
        ]

        if not matching_files:
            return CheckResult(
                CheckStatus.NOT_ELIGIBLE,
                "No workflow uses canonical/operator-workflows/.github/workflows/test.yaml.",
            )

        offending = []
        for workflow_file in matching_files:
            try:
                data = yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            if _find_self_hosted_runner(data):
                offending.append(workflow_file.name)

        if offending:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"self-hosted-runner is enabled in: {', '.join(sorted(offending))}.",
            )
        return CheckResult(CheckStatus.COMPLIANT, "No self-hosted runners configured.")
