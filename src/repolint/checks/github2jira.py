# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a GitHub-to-Jira sync configuration."""

import re

import yaml

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import clone_repository_locally

TEMPLATE_VERSION_RE = re.compile(r"^#\s*template-version:\s*1\s*$", re.MULTILINE)


class Github2JiraCheck(Check):
    """Check that the repository has an up-to-date GitHub-to-Jira sync configuration."""

    name = "github2jira"
    parent = "github"
    description = (
        "Repository has GitHub to Jira integration set up using the latest template format. "
        "To fix it, copy .github/.jira_sync_config.yaml from "
        "https://github.com/canonical/platform-engineering-charm-template."
    )

    def run(self, repo: str) -> CheckResult:
        """Check that the sync configuration exists and follows the latest format."""
        local_repo = clone_repository_locally(repo)
        integration_conf_file = local_repo / ".github/.jira_sync_config.yaml"
        if not integration_conf_file.exists():
            return CheckResult(
                CheckStatus.NOT_COMPLIANT, "No GitHub to Jira integration config found."
            )

        content = integration_conf_file.read_text(encoding="utf-8")
        problems = []
        if not TEMPLATE_VERSION_RE.search(content):
            problems.append("missing '# template-version: 1' header")

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return CheckResult(CheckStatus.NOT_COMPLIANT, "Jira sync config is not valid YAML.")
        settings = data.get("settings") if isinstance(data, dict) else None
        if not isinstance(settings, dict):
            settings = {}

        if not settings.get("labels"):
            problems.append("'settings.labels' is not configured")
        if "component" in settings:
            problems.append("'settings.component' is not supported, use 'settings.components'")
        component = settings.get("components")
        if "component" not in settings and (
            not isinstance(component, list) or len(component) != 1
        ):
            problems.append("'settings.components' must be a list with exactly one component")
        if "epic_key" in settings:
            problems.append("'settings.epic_key' must not be set")

        if problems:
            return CheckResult(CheckStatus.NOT_COMPLIANT, "; ".join(problems) + ".")
        return CheckResult(CheckStatus.COMPLIANT, "")
