# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.checks — Check base class and registry."""

from unittest.mock import patch

import pytest

from repolint.checks import Check, CheckResult, get_check_function
from repolint.config import CheckStatus

# ---------------------------------------------------------------------------
# Helpers — minimal concrete Check subclasses for testing cross-cutting logic
# ---------------------------------------------------------------------------


def _make_simple_check(check_name: str, result: CheckStatus = CheckStatus.COMPLIANT) -> Check:
    """Dynamically create a minimal Check subclass with a fixed run() result."""

    class _SimpleCheck(Check):
        name = check_name  # type: ignore[assignment]

        def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
            return CheckResult(result, "ran")

    # Remove from registry so test helpers don't pollute other tests.
    from repolint.checks._base import _REGISTRY

    return _REGISTRY.pop(check_name)  # returns the auto-registered instance


# ---------------------------------------------------------------------------
# Check.__call__ — exclusion
# ---------------------------------------------------------------------------


class TestCheckExclusion:
    def test_excluded_repo_returns_not_eligible(self):
        check = _make_simple_check("_test_excl_a")
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_excl_a", "excluded": ["canonical/excluded-repo"]},
        ):
            result = check("canonical/excluded-repo")
        assert result.result == CheckStatus.NOT_ELIGIBLE

    def test_non_excluded_repo_runs_check(self):
        check = _make_simple_check("_test_excl_b")
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_excl_b", "excluded": ["canonical/other-repo"]},
        ):
            result = check("canonical/allowed-repo")
        assert result.result == CheckStatus.COMPLIANT
        assert result.message == "ran"


# ---------------------------------------------------------------------------
# Check.__call__ — dependency handling
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    def test_dependency_not_compliant_skips_check(self):
        check = _make_simple_check("_test_dep_a")
        previous = {"dep_check": CheckResult(CheckStatus.NOT_COMPLIANT, "")}
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_dep_a", "depends_on": ["dep_check"]},
        ):
            result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_ELIGIBLE
        assert "dep_check" in result.message

    def test_dependency_compliant_runs_check(self):
        check = _make_simple_check("_test_dep_b")
        previous = {"dep_check": CheckResult(CheckStatus.COMPLIANT, "")}
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_dep_b", "depends_on": ["dep_check"]},
        ):
            result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.COMPLIANT

    def test_missing_dependency_raises(self):
        check = _make_simple_check("_test_dep_c")
        with (
            patch(
                "repolint.checks._base.get_criterion_by_name",
                return_value={"name": "_test_dep_c", "depends_on": ["missing_dep"]},
            ),
            pytest.raises(RuntimeError, match="missing_dep"),
        ):
            check("canonical/some-repo", previous_results={})


# ---------------------------------------------------------------------------
# Check.__call__ — aggregate handling
# ---------------------------------------------------------------------------


class TestCheckAggregates:
    def test_all_subchecks_compliant_returns_compliant(self):
        check = _make_simple_check("_test_agg_a")
        previous = {
            "sub_a": CheckResult(CheckStatus.COMPLIANT, ""),
            "sub_b": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_agg_a", "aggregates": ["sub_a", "sub_b"]},
        ):
            result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.COMPLIANT

    def test_one_subcheck_failing_returns_not_compliant(self):
        check = _make_simple_check("_test_agg_b")
        previous = {
            "sub_a": CheckResult(CheckStatus.COMPLIANT, ""),
            "sub_b": CheckResult(CheckStatus.NOT_COMPLIANT, "failed"),
        }
        with patch(
            "repolint.checks._base.get_criterion_by_name",
            return_value={"name": "_test_agg_b", "aggregates": ["sub_a", "sub_b"]},
        ):
            result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "sub_b" in result.message

    def test_missing_subcheck_raises(self):
        check = _make_simple_check("_test_agg_c")
        with (
            patch(
                "repolint.checks._base.get_criterion_by_name",
                return_value={"name": "_test_agg_c", "aggregates": ["missing_sub"]},
            ),
            pytest.raises(RuntimeError),
        ):
            check("canonical/some-repo", previous_results={})


# ---------------------------------------------------------------------------
# Check.description — class attribute
# ---------------------------------------------------------------------------


class TestCheckDescription:
    def test_description_is_class_attribute(self):
        class _DescCheck(Check):
            name = "_test_desc_a"  # type: ignore[assignment]
            description = "A test description."

            def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
                return CheckResult(CheckStatus.COMPLIANT, "")

        from repolint.checks._base import _REGISTRY

        check = _REGISTRY.pop("_test_desc_a")
        assert check.description == "A test description."

    def test_leaf_checks_have_non_empty_description(self):
        """Every leaf check registered in the package must have a non-empty description."""
        from repolint.criteria import list_criteria

        for criterion in list_criteria():
            instance = get_check_function(criterion["name"])
            assert instance is not None
            assert isinstance(instance.description, str), (
                f"{criterion['name']}.description is not a str"
            )
            assert instance.description, f"{criterion['name']}.description is empty"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestGetCheckFunction:
    def test_known_check_is_registered(self):
        instance = get_check_function("pfe_topic")
        assert instance is not None
        assert callable(instance)
        assert isinstance(instance, Check)

    def test_unknown_check_returns_none(self):
        instance = get_check_function("nonexistent_check_xyz")
        assert instance is None

    def test_all_criteria_are_registered(self):
        """Every criterion (leaf and aggregate) must have a registered Check instance."""
        from repolint.criteria import list_criteria

        for criterion in list_criteria():
            name = criterion["name"]
            instance = get_check_function(name)
            assert instance is not None, f"No Check registered for criterion {name!r}"
            assert isinstance(instance, Check)

    def test_check_name_matches_criterion(self):
        """The name attribute of each registered Check must match the registry key."""
        from repolint.criteria import list_criteria

        for criterion in list_criteria():
            name = criterion["name"]
            instance = get_check_function(name)
            assert instance is not None
            assert instance.name == name
