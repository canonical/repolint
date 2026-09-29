# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: charm(s) declare support for the most recent Ubuntu base."""

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_charmcraft_paths

# Most recent Ubuntu base that "live" charms are expected to support.
TARGET_BASE = "26.04"


def _supports_target_base(data: dict) -> bool:
    """Return True if a parsed charmcraft.yaml declares support for TARGET_BASE.

    Only the modern ``platforms`` key is considered; platform keys look like
    ``ubuntu@26.04:amd64`` so a substring match is enough.
    """
    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        return False
    return any(TARGET_BASE in str(platform_key) for platform_key in platforms)


class SupportedBasesCheck(Check):
    """Check that all charms in the repository support the most recent Ubuntu base."""

    name = "supported_bases"
    parent = "dependencies"
    depends_on = ["contains_charm", "actively_maintained"]  # noqa: RUF012
    description = f"Repository's charm(s) support the most recent Ubuntu base ({TARGET_BASE})."

    def run(self, repo: str) -> CheckResult:
        """Check that all charms in the repository support the target Ubuntu base."""
        local_repo = clone_repository_locally(repo)
        charms = find_charmcraft_paths(local_repo)
        non_compliant: list[str] = []
        for charm in charms:
            try:
                data = yaml.safe_load(charm.read_text())
            except (yaml.YAMLError, UnicodeDecodeError):
                non_compliant.append(f"{charm}: could not parse charmcraft.yaml")
                continue
            if not isinstance(data, dict):
                non_compliant.append(f"{charm}: could not parse charmcraft.yaml")
                continue
            if "bases" in data:
                non_compliant.append(f"{charm}: uses the deprecated 'bases' key")
                continue
            if not _supports_target_base(data):
                non_compliant.append(f"{charm}: does not declare '{TARGET_BASE}' in 'platforms'")

        if non_compliant:
            return CheckResult(CheckStatus.NOT_COMPLIANT, "; ".join(non_compliant))
        return CheckResult(
            CheckStatus.COMPLIANT,
            f"All charms declare support for {TARGET_BASE} in 'platforms'.",
        )
