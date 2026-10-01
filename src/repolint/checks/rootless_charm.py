# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: charm(s) declare a non-root 'charm-user' in charmcraft.yaml."""

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_charmcraft_paths


class RootlessCharmCheck(Check):
    """Check that all charms in the repository run as a non-root user."""

    name = "rootless_charm"
    parent = "security"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository's charm(s) declare a non-root 'charm-user' in charmcraft.yaml."

    def run(self, repo: str) -> CheckResult:
        """Check that all charms declare a 'charm-user' key with a non-root value."""
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
            charm_user = data.get("charm-user")
            if charm_user is None:
                non_compliant.append(f"{charm}: missing 'charm-user' key, defaults to root")
                continue
            if charm_user == "root":
                non_compliant.append(f"{charm}: 'charm-user' is set to 'root'")

        if non_compliant:
            return CheckResult(CheckStatus.NOT_COMPLIANT, "; ".join(non_compliant))
        return CheckResult(CheckStatus.COMPLIANT, "All charms declare a non-root 'charm-user'.")
