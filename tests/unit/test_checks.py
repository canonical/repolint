# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.checks (decorator and registry)."""

from unittest.mock import patch

import pytest

from repolint.checks import CheckResult, check, get_check_function
from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT, CHECK_NOT_ELIGIBLE

# ---------------------------------------------------------------------------
# Helpers - lightweight check functions created purely for testing
# ---------------------------------------------------------------------------


def _make_check(name: str, result: str = CHECK_COMPLIANT, message: str = "") -> CheckResult:
    """Build a trivial CheckResult."""
    return {"result": result, "message": message}


# ---------------------------------------------------------------------------
# @check decorator behaviour
# ---------------------------------------------------------------------------


class TestCheckDecoratorExclusion:
    def test_excluded_repo_returns_not_eligible(self):
        @check
        def check_repository_test_exclusion_a(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": ""}

        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_exclusion_a", "excluded": ["canonical/excluded-repo"]},
        ):
            result = check_repository_test_exclusion_a("canonical/excluded-repo")

        assert result["result"] == CHECK_NOT_ELIGIBLE

    def test_non_excluded_repo_runs_check(self):
        @check
        def check_repository_test_exclusion_b(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": "ran"}

        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_exclusion_b", "excluded": ["canonical/other-repo"]},
        ):
            result = check_repository_test_exclusion_b("canonical/allowed-repo")

        assert result["result"] == CHECK_COMPLIANT
        assert result["message"] == "ran"


class TestCheckDecoratorDependencies:
    def test_dependency_not_compliant_skips_check(self):
        @check
        def check_repository_test_dep_a(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": "should not run"}

        previous = {"dep_check": {"result": CHECK_NOT_COMPLIANT, "message": ""}}
        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_dep_a", "depends_on": ["dep_check"]},
        ):
            result = check_repository_test_dep_a("canonical/some-repo", previous_results=previous)

        assert result["result"] == CHECK_NOT_ELIGIBLE
        assert "dep_check" in result["message"]

    def test_dependency_compliant_runs_check(self):
        @check
        def check_repository_test_dep_b(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": "ran successfully"}

        previous = {"dep_check": {"result": CHECK_COMPLIANT, "message": ""}}
        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_dep_b", "depends_on": ["dep_check"]},
        ):
            result = check_repository_test_dep_b("canonical/some-repo", previous_results=previous)

        assert result["result"] == CHECK_COMPLIANT

    def test_missing_dependency_raises(self):
        @check
        def check_repository_test_dep_c(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": ""}

        with (
            patch(
                "repolint.checks.get_criterion_by_name",
                return_value={"name": "test_dep_c", "depends_on": ["missing_dep"]},
            ),
            pytest.raises(RuntimeError, match="missing_dep"),
        ):
            check_repository_test_dep_c("canonical/some-repo", previous_results={})


class TestCheckDecoratorAggregates:
    def test_all_subchecks_compliant_returns_compliant(self):
        @check
        def check_repository_test_agg_a(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": ""}

        previous = {
            "sub_a": {"result": CHECK_COMPLIANT, "message": ""},
            "sub_b": {"result": CHECK_COMPLIANT, "message": ""},
        }
        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_agg_a", "aggregates": ["sub_a", "sub_b"]},
        ):
            result = check_repository_test_agg_a("canonical/some-repo", previous_results=previous)

        assert result["result"] == CHECK_COMPLIANT

    def test_one_subcheck_failing_returns_not_compliant(self):
        @check
        def check_repository_test_agg_b(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": ""}

        previous = {
            "sub_a": {"result": CHECK_COMPLIANT, "message": ""},
            "sub_b": {"result": CHECK_NOT_COMPLIANT, "message": "failed"},
        }
        with patch(
            "repolint.checks.get_criterion_by_name",
            return_value={"name": "test_agg_b", "aggregates": ["sub_a", "sub_b"]},
        ):
            result = check_repository_test_agg_b("canonical/some-repo", previous_results=previous)

        assert result["result"] == CHECK_NOT_COMPLIANT
        assert "sub_b" in result["message"]

    def test_missing_subcheck_raises(self):
        @check
        def check_repository_test_agg_c(repo, previous_results=None) -> CheckResult:
            return {"result": CHECK_COMPLIANT, "message": ""}

        with (
            patch(
                "repolint.checks.get_criterion_by_name",
                return_value={"name": "test_agg_c", "aggregates": ["missing_sub"]},
            ),
            pytest.raises(RuntimeError),
        ):
            check_repository_test_agg_c("canonical/some-repo", previous_results={})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestGetCheckFunction:
    def test_known_check_is_registered(self):
        fn = get_check_function("pfe_topic")
        assert fn is not None
        assert callable(fn)

    def test_unknown_check_returns_none(self):
        fn = get_check_function("nonexistent_check_xyz")
        assert fn is None

    def test_all_non_aggregate_criteria_are_registered(self):
        from repolint.criteria import list_criteria

        for criterion in list_criteria():
            if not criterion.get("aggregates"):
                name = criterion["name"]
                fn = get_check_function(name)
                assert fn is not None, f"No check function registered for criterion {name!r}"
