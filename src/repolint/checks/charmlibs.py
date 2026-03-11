# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository does not use deprecated operator_libs_linux."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally, find_regexp_in_path


class CharmLibsCheck(Check):
    """Check that the repository does not use deprecated operator_libs_linux.

    References:
    - https://documentation.ubuntu.com/charmlibs/reference/general-libs/
    - https://documentation.ubuntu.com/charmlibs/reference/interface-libs/
    """

    name = "charmlibs"
    parent = "dependencies"
    depends_on = ["contains_charm"]  # noqa: RUF012
    description = "Repository uses charmlibs for shared code."

    def run(self, repo: str) -> CheckResult:
        """Check that the repository does not use deprecated operator_libs_linux."""
        local_repo = clone_repository_locally(repo)
        pattern = "from charms.operator_libs_linux"
        if find_regexp_in_path(local_repo, pattern=pattern, recursive=True):
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                "Found imports of charms.operator_libs_linux.",
            )
        return CheckResult(
            CheckStatus.COMPLIANT, "No reference to charms.operator_libs_linux found."
        )
