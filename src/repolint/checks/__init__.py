# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Repository compliance checks package.

Importing this package registers all leaf checks via ``Check.__init_subclass__``
and registers ``AggregateCheck`` instances (which self-register on construction).
"""

# Import leaf-check modules to trigger auto-registration via __init_subclass__.
from repolint.checks import (  # noqa: F401
    charmlibs,
    ck8s,
    contains_charm,
    contains_k8s_charm,
    github2jira,
    jubilant,
    juju4,
    ops_testing,
    pfe_topic,
    product_topic,
    squad_topic,
    tf_v1,
)
from repolint.checks._base import (
    AggregateCheck,
    Check,
    CheckResult,
    configure_checks,
    get_check,
    list_checks,
)
from repolint.config import CheckStatus

# Register aggregate checks — AggregateCheck.__init__ adds each to _REGISTRY.
AggregateCheck(
    "github",
    description="Repository matches all our GitHub best practices (topics, GitHub to Jira integration).",
    depends_on=["pfe_topic"],
    aggregates=["pfe_topic", "squad_topic", "product_topic", "github2jira"],
)
AggregateCheck(
    "unit_tests",
    description="Repository follows our unit testing best practices.",
    depends_on=["contains_charm"],
    aggregates=["ops_testing"],
)
AggregateCheck(
    "integration_tests",
    description="Repository follows our integration testing best practices.",
    depends_on=["contains_charm"],
    aggregates=["jubilant", "juju4", "ck8s"],
)
AggregateCheck(
    "terraform",
    description="Repository follows our Terraform best practices.",
    depends_on=["contains_charm"],
    aggregates=["tf_v1"],
)

__all__ = [
    "AggregateCheck",
    "Check",
    "CheckResult",
    "CheckStatus",
    "configure_checks",
    "get_check",
    "list_checks",
]
