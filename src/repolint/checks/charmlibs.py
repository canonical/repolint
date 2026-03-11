# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository does not use deprecated operator_libs_linux."""

import subprocess

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import clone_repository_locally, find_regexp_in_path


class CharmLibsCheck(Check):
    """Check that the repository does not use deprecated operator_libs_linux.

    References:
    - https://documentation.ubuntu.com/charmlibs/reference/general-libs/
    - https://documentation.ubuntu.com/charmlibs/reference/interface-libs/
    """

    name = "charmlibs"

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository does not use deprecated operator_libs_linux."""
        try:
            local_repo = clone_repository_locally(repo)
        except subprocess.CalledProcessError as e:
            return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
        pattern = "from charms.operator_libs_linux"
        if find_regexp_in_path(local_repo, pattern=pattern, recursive=True):
            return {
                "result": CHECK_NOT_COMPLIANT,
                "message": "Found imports of charms.operator_libs_linux.",
            }
        return {
            "result": CHECK_COMPLIANT,
            "message": "No reference to charms.operator_libs_linux found.",
        }
