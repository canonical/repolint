# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Repository compliance checks package.

Importing this package registers all leaf checks via ``Check.__init_subclass__``
and registers ``AggregateCheck`` instances for every aggregate criterion defined
in the criteria catalogue.
"""

# Re-export public API from the base module.
# Import all leaf-check modules so their classes are defined and auto-registered.
from repolint.checks import (
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
from repolint.checks._base import _REGISTRY, AggregateCheck, Check, CheckResult, get_check_function
from repolint.config import CheckStatus

# Register AggregateCheck instances for every aggregate criterion.
from repolint.criteria import list_criteria

for _criterion in list_criteria():
    if _criterion.get("aggregates"):
        _REGISTRY[_criterion["name"]] = AggregateCheck(
            _criterion["name"], _criterion["description"]
        )

__all__ = [
    "AggregateCheck",
    "Check",
    "CheckResult",
    "CheckStatus",
    "charmlibs",
    "ck8s",
    "contains_charm",
    "contains_k8s_charm",
    "get_check_function",
    "github2jira",
    "jubilant",
    "juju4",
    "ops_testing",
    "pfe_topic",
    "product_topic",
    "squad_topic",
    "tf_v1",
]
