# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has tests targeting Juju 4."""

from pathlib import Path

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_files_in_path, find_regexp_in_path


def _concierge_targets_juju4(concierge_file: Path) -> bool:
    """Return True if the concierge file has a ``juju.channel`` starting with 4."""
    try:
        content = yaml.safe_load(concierge_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return False
    if not isinstance(content, dict):
        return False
    juju_section = content.get("juju")
    if not isinstance(juju_section, dict):
        return False
    channel = juju_section.get("channel")
    return channel is not None and str(channel).startswith("4")


class Juju4Check(Check):
    """Check that the repository has at least one test setup targeting Juju 4."""

    name = "juju4"
    parent = "integration_tests"
    depends_on = ["contains_charm", "charmci", "actively_maintained"]  # noqa: RUF012
    description = "Repository has tests for Juju 4."

    def run(self, repo: str) -> CheckResult:
        """Check spread.yaml and concierge-*.yaml files for Juju 4."""
        local_repo = clone_repository_locally(repo)
        spread_file = local_repo / "spread.yaml"
        if spread_file.is_file() and find_regexp_in_path(spread_file, "juju4"):
            return CheckResult(CheckStatus.COMPLIANT, "spread.yaml references juju4.")
        for concierge_file in find_files_in_path(local_repo, "concierge-*.yaml"):
            if _concierge_targets_juju4(concierge_file):
                relative_name = concierge_file.relative_to(local_repo)
                return CheckResult(
                    CheckStatus.COMPLIANT, f"{relative_name} sets juju.channel to Juju 4."
                )
        return CheckResult(
            CheckStatus.NOT_COMPLIANT,
            "No reference to juju4 in spread.yaml and no concierge-*.yaml "
            "with a juju.channel starting with 4.",
        )
