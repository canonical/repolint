# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Criteria definitions for repository compliance checks."""


def list_criteria() -> list[dict]:
    """List criteria to check against.

    Format:
    - name: name of the criterion (must match the check function name suffix)
    - description: description of the criterion
    - depends_on: list of criteria names that this criterion depends on
                  (should appear before in the list as they are checked in order).
                  The check will only be run if all previous checks pass.
    - aggregates: list of criteria names that this criterion aggregates (should appear before
                  in the list). The check automatically fails if any aggregated checks fail, and
                  passes if all aggregated checks pass.
    - excluded: list of repositories (full names) to exclude from this criterion
    - hidden: if True, the criterion is not shown in the overview report
    """
    return [
        {
            "name": "pfe_topic",
            "description": "Repository has a platform-engineering topic. To fix it. Add the topic to the repository via canonical-repo-automation.",
            "excluded": ["canonical/cbartz-runner-testing", "wazuh-dev"],
            "hidden": True,
        },
        {
            "name": "squad_topic",
            "description": "Repository has a squad-xxx topic. To fix it. Add the topic to the repository via canonical-repo-automation.",
            "depends_on": ["pfe_topic"],
            "hidden": True,
        },
        {
            "name": "product_topic",
            "description": "Repository has a product-xxx topic. To fix it. Add the topic to the repository via canonical-repo-automation.",
            "depends_on": ["pfe_topic"],
            "hidden": True,
        },
        {
            "name": "contains_charm",
            "description": "Repository contains at least one charm (charmcraft.yaml file).",
            "hidden": True,
        },
        {
            "name": "contains_k8s_charm",
            "description": "Repository contains at least one charm (charmcraft.yaml file).",
            "hidden": True,
            "depends_on": ["contains_charm"],
        },
        {
            "name": "github2jira",
            "description": "Repository has GitHub to Jira integration set up. To fix it. Add .github/.jira_sync_config.yaml to the repository.",
            "depends_on": ["pfe_topic"],
            "excluded": ["canonical/gatekeeper-repo-test"],
            "hidden": True,
        },
        {
            "name": "charmlibs",
            "description": "Repository uses charmlibs for shared code.",
            "depends_on": ["contains_charm"],
        },
        {
            "name": "ops_testing",
            "description": "Repository doesn't use harness.",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "jubilant",
            "description": "Repository uses Jubilant for charm testing.",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "tf_v1",
            "description": "Repository uses Terraform Juju provider v1.",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "juju4",
            "description": "Repository has tests for Juju 4.",
            "depends_on": ["contains_charm"],
            "hidden": True,
        },
        {
            "name": "ck8s",
            "description": "Repository uses CK8s.",
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


def get_criterion_by_name(name: str) -> dict | None:
    """Get criterion by name."""
    for criterion in list_criteria():
        if criterion["name"] == name:
            return criterion
    return None


def list_criteria_names() -> list[str]:
    """List criteria names."""
    return [criterion["name"] for criterion in list_criteria()]
