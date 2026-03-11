# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Criteria definitions for repository compliance checks."""

# Per-check configuration loaded from repolint.yaml.  Populated by
# configure_checks() which is called from the CLI entry point before any
# analysis runs.
_checks_overrides: dict[str, dict] = {}


def configure_checks(checks_config: dict[str, dict]) -> None:
    """Set per-check configuration sourced from the repolint.yaml ``checks`` key.

    *checks_config* is expected to be a mapping of check name → check options.
    Currently only ``excluded`` (a list of ``org/repo`` strings) is supported::

        {
            "pfe_topic": {"excluded": ["canonical/cbartz-runner-testing"]},
            "github2jira": {"excluded": ["canonical/gatekeeper-repo-test"]},
        }

    Calling this function again replaces any previously configured overrides.
    """
    global _checks_overrides
    _checks_overrides = checks_config


def list_criteria() -> list[dict]:
    """List criteria to check against, with exclusions merged from the loaded config.

    Format:
    - name: name of the criterion (must match the Check subclass name attribute)
    - depends_on: list of criteria names that this criterion depends on
                  (should appear before in the list as they are checked in order).
                  The check will only be run if all previous checks pass.
    - aggregates: list of criteria names that this criterion aggregates (should appear before
                  in the list). The check automatically fails if any aggregated checks fail, and
                  passes if all aggregated checks pass.
    - excluded: list of repositories (full names) to exclude from this criterion.
                Merged with any exclusions provided via configure_checks().
    - hidden: if True, the criterion is not shown in the overview report

    Note: descriptions live in each Check subclass (leaf checks) or are passed
    to AggregateCheck at construction time.
    """
    base: list[dict] = [
        {
            "name": "pfe_topic",
            "excluded": ["canonical/cbartz-runner-testing", "wazuh-dev"],
            "hidden": True,
        },
        {
            "name": "squad_topic",
            "depends_on": ["pfe_topic"],
            "hidden": True,
        },
        {
            "name": "product_topic",
            "depends_on": ["pfe_topic"],
            "hidden": True,
        },
        {
            "name": "contains_charm",
            "hidden": True,
        },
        {
            "name": "contains_k8s_charm",
            "hidden": True,
            "depends_on": ["contains_charm"],
        },
        {
            "name": "github2jira",
            "depends_on": ["pfe_topic"],
            "excluded": ["canonical/gatekeeper-repo-test"],
            "hidden": True,
        },
        {
            "name": "charmlibs",
            "depends_on": ["contains_charm"],
        },
        {
            "name": "ops_testing",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "jubilant",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "tf_v1",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "juju4",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "ck8s",
            "doc_link": " https://canonical-platform-engineering.readthedocs-hosted.com/latest/engineering-practices/migration-guides/migrate-to-canonical-kubernetes/",
            "depends_on": ["contains_k8s_charm"],
            "hidden": True,
        },
        {
            "name": "github",
            "description": "Repository matches all our GitHub best practices (topics, GitHub to Jira integration).",
            "depends_on": ["pfe_topic"],
            "aggregates": ["pfe_topic", "squad_topic", "product_topic", "github2jira"],
        },
        {
            "name": "unit_tests",
            "description": "Repository follows our unit testing best practices.",
            "depends_on": ["contains_charm"],
            "aggregates": ["ops_testing"],
        },
        {
            "name": "integration_tests",
            "description": "Repository follows our integration testing best practices.",
            "depends_on": ["contains_charm"],
            "aggregates": ["jubilant", "juju4", "ck8s"],
        },
        {
            "name": "terraform",
            "description": "Repository follows our Terraform best practices.",
            "depends_on": ["contains_charm"],
            "aggregates": ["tf_v1"],
        },
    ]
    if not _checks_overrides:
        return base
    merged: list[dict] = []
    for criterion in base:
        override = _checks_overrides.get(criterion["name"], {})
        config_excluded: list[str] = override.get("excluded", [])
        if config_excluded:
            criterion = dict(criterion)  # shallow copy to avoid mutating the literal
            criterion["excluded"] = list(
                dict.fromkeys(criterion.get("excluded", []) + config_excluded)
            )
        merged.append(criterion)
    return merged


def get_criterion_by_name(name: str) -> dict | None:
    """Get criterion by name."""
    for criterion in list_criteria():
        if criterion["name"] == name:
            return criterion
    return None


def list_criteria_names() -> list[str]:
    """List criteria names."""
    return [criterion["name"] for criterion in list_criteria()]
