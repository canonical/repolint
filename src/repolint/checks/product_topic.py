# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a product-* GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CheckStatus
from repolint.utils import get_repository_topics


class ProductTopicCheck(Check):
    """Check that the repository has a product-xxx topic."""

    name = "product_topic"
    hidden = True
    description = "Repository has a product-xxx topic. To fix it, add the topic via canonical-repo-automation."

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has a product-xxx topic."""
        topics = get_repository_topics(repo)
        if any(topic.startswith("product-") for topic in topics):
            return CheckResult(CheckStatus.COMPLIANT, "")
        return CheckResult(CheckStatus.NOT_COMPLIANT, "No product topic found.")
