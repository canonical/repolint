# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Repository compliance checks package.

Importing this package registers all leaf checks via ``Check.__init_subclass__``
and registers ``ParentCheck`` instances (which self-register on construction).
"""

# Import leaf-check modules to trigger auto-registration via __init_subclass__.
from repolint.checks import (  # noqa: F401
    charmlibs,
    ck8s,
    contains_charm,
    contains_k8s_charm,
    github2jira,
    github_topics,
    jubilant,
    juju4,
    ops_testing,
    tf_v1,
)
from repolint.checks._base import (
    Check,
    CheckResult,
    ParentCheck,
    configure_checks,
    get_check,
    list_checks,
)
from repolint.config import CheckStatus

# Register parent checks — ParentCheck.__init__ adds each to _REGISTRY.
ParentCheck(
    "github",
    description="Repository matches all our GitHub best practices (topics, GitHub to Jira integration).",
)
ParentCheck(
    "unit_tests",
    description="Repository follows our unit testing best practices.",
    depends_on=["contains_charm"],
)
ParentCheck(
    "integration_tests",
    description="Repository follows our integration testing best practices.",
    depends_on=["contains_charm"],
)
ParentCheck(
    "terraform",
    description="Repository follows our Terraform best practices.",
    depends_on=["contains_charm"],
)
ParentCheck(
    "dependencies",
    description="Repository uses up-to-date charm libraries and avoids deprecated dependencies.",
    depends_on=["contains_charm"],
)

__all__ = [
    "Check",
    "CheckResult",
    "CheckStatus",
    "ParentCheck",
    "configure_checks",
    "get_check",
    "list_checks",
]
