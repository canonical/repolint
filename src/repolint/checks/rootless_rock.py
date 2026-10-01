# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: rock(s) declare a non-root 'run-user' in rockcraft.yaml."""

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_rockcraft_paths


class RootlessRockCheck(Check):
    """Check that all rocks in the repository run as a non-root user."""

    name = "rootless_rock"
    parent = "security"
    depends_on = ["contains_rock"]  # noqa: RUF012
    description = "Repository's rock(s) declare a non-root 'run-user' in rockcraft.yaml."

    def run(self, repo: str) -> CheckResult:
        """Check that all rocks declare a 'run-user' key with a non-root value."""
        local_repo = clone_repository_locally(repo)
        rocks = find_rockcraft_paths(local_repo)
        non_compliant: list[str] = []
        for rock in rocks:
            try:
                data = yaml.safe_load(rock.read_text())
            except (yaml.YAMLError, UnicodeDecodeError):
                non_compliant.append(f"{rock}: could not parse rockcraft.yaml")
                continue
            if not isinstance(data, dict):
                non_compliant.append(f"{rock}: could not parse rockcraft.yaml")
                continue
            run_user = data.get("run-user")
            if run_user is None:
                non_compliant.append(f"{rock}: missing 'run-user' key, defaults to root")
                continue
            if run_user == "root":
                non_compliant.append(f"{rock}: 'run-user' is set to 'root'")

        if non_compliant:
            return CheckResult(CheckStatus.NOT_COMPLIANT, "; ".join(non_compliant))
        return CheckResult(CheckStatus.COMPLIANT, "All rocks declare a non-root 'run-user'.")
