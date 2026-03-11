# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check: repository has a product-* GitHub topic."""

from repolint.checks._base import Check, CheckResult
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT
from repolint.utils import get_repository_topics


class ProductTopicCheck(Check):
    """Check that the repository has a product-xxx topic."""

    name = "product_topic"

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Check that the repository has a product-xxx topic."""
        topics = get_repository_topics(repo)
        if any(topic.startswith("product-") for topic in topics):
            return {"result": CHECK_COMPLIANT, "message": ""}
        return {"result": CHECK_NOT_COMPLIANT, "message": "No product topic found."}
