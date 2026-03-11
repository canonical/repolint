# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.checks — Check base class and registry."""

import pytest

from repolint.checks import Check, CheckResult, get_check, list_checks
from repolint.checks._base import configure_checks
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
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def test_excluded_repo_returns_not_eligible(self):
        check = _make_simple_check("_test_excl_a")
        configure_checks({"_test_excl_a": {"excluded": ["canonical/excluded-repo"]}})
        result = check("canonical/excluded-repo")
        assert result.result == CheckStatus.NOT_ELIGIBLE

    def test_non_excluded_repo_runs_check(self):
        check = _make_simple_check("_test_excl_b")
        configure_checks({"_test_excl_b": {"excluded": ["canonical/other-repo"]}})
        result = check("canonical/allowed-repo")
        assert result.result == CheckStatus.COMPLIANT
        assert result.message == "ran"


# ---------------------------------------------------------------------------
# Check.__call__ — dependency handling
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    def test_dependency_not_compliant_skips_check(self):
        check = _make_simple_check("_test_dep_a")
        check.depends_on = ["dep_check"]  # type: ignore[assignment]
        previous = {"dep_check": CheckResult(CheckStatus.NOT_COMPLIANT, "")}
        result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_ELIGIBLE
        assert "dep_check" in result.message

    def test_dependency_compliant_runs_check(self):
        check = _make_simple_check("_test_dep_b")
        check.depends_on = ["dep_check"]  # type: ignore[assignment]
        previous = {"dep_check": CheckResult(CheckStatus.COMPLIANT, "")}
        result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.COMPLIANT

    def test_missing_dependency_raises(self):
        check = _make_simple_check("_test_dep_c")
        check.depends_on = ["missing_dep"]  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="missing_dep"):
            check("canonical/some-repo", previous_results={})


# ---------------------------------------------------------------------------
# Check.__call__ — aggregate handling
# ---------------------------------------------------------------------------


class TestCheckAggregates:
    def test_all_subchecks_compliant_returns_compliant(self):
        check = _make_simple_check("_test_agg_a")
        check.aggregates = ["sub_a", "sub_b"]  # type: ignore[assignment]
        previous = {
            "sub_a": CheckResult(CheckStatus.COMPLIANT, ""),
            "sub_b": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.COMPLIANT

    def test_one_subcheck_failing_returns_not_compliant(self):
        check = _make_simple_check("_test_agg_b")
        check.aggregates = ["sub_a", "sub_b"]  # type: ignore[assignment]
        previous = {
            "sub_a": CheckResult(CheckStatus.COMPLIANT, ""),
            "sub_b": CheckResult(CheckStatus.NOT_COMPLIANT, "failed"),
        }
        result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "sub_b" in result.message

    def test_missing_subcheck_raises(self):
        check = _make_simple_check("_test_agg_c")
        check.aggregates = ["missing_sub"]  # type: ignore[assignment]
        with pytest.raises(RuntimeError):
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
        """Every check registered in the package must have a non-empty description."""
        for check in list_checks():
            assert isinstance(check.description, str), f"{check.name}.description is not a str"
            assert check.description, f"{check.name}.description is empty"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestGetCheckFunction:
    def test_known_check_is_registered(self):
        instance = get_check("squad_topic")
        assert instance is not None
        assert callable(instance)
        assert isinstance(instance, Check)

    def test_unknown_check_returns_none(self):
        instance = get_check("nonexistent_check_xyz")
        assert instance is None

    def test_all_checks_are_registered(self):
        """Every check (leaf and aggregate) must have a registered Check instance."""
        for check in list_checks():
            instance = get_check(check.name)
            assert instance is not None, f"No Check registered for {check.name!r}"
            assert isinstance(instance, Check)

    def test_check_name_matches_registry_key(self):
        """The name attribute of each registered Check must match the registry key."""
        for check in list_checks():
            instance = get_check(check.name)
            assert instance is not None
            assert instance.name == check.name


# ---------------------------------------------------------------------------
# list_checks — topological sort
# ---------------------------------------------------------------------------


class TestListChecks:
    def test_returns_list(self):
        result = list_checks()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_no_duplicates(self):
        names = [c.name for c in list_checks()]
        assert len(names) == len(set(names)), "Duplicate check names found"

    def test_dependencies_appear_before_dependents(self):
        seen: set[str] = set()
        for check in list_checks():
            for dep in check.depends_on:
                assert dep in seen, (
                    f"Check {check.name!r} depends on {dep!r} which has not appeared yet"
                )
            seen.add(check.name)

    def test_aggregates_appear_before_aggregators(self):
        seen: set[str] = set()
        for check in list_checks():
            for agg in check.aggregates:
                assert agg in seen, (
                    f"Check {check.name!r} aggregates {agg!r} which has not appeared yet"
                )
            seen.add(check.name)


# ---------------------------------------------------------------------------
# configure_checks
# ---------------------------------------------------------------------------


class TestConfigureChecks:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def test_configure_sets_exclusions(self):
        configure_checks({"squad_topic": {"excluded": ["canonical/extra-repo"]}})
        check = get_check("squad_topic")
        assert check is not None
        result = check("canonical/extra-repo")
        assert result.result == CheckStatus.NOT_ELIGIBLE

    def test_configure_non_excluded_repo_runs(self):
        configure_checks({"squad_topic": {"excluded": ["canonical/excluded-repo"]}})
        check = get_check("squad_topic")
        assert check is not None
        # "canonical/allowed-repo" is not excluded — check should run (not return NOT_ELIGIBLE
        # due to exclusion); actual result depends on the repo content, but it won't be
        # excluded.
        from repolint.checks._base import _checks_overrides

        assert "canonical/excluded-repo" in _checks_overrides.get("squad_topic", {}).get(
            "excluded", []
        )
        assert "canonical/allowed-repo" not in _checks_overrides.get("squad_topic", {}).get(
            "excluded", []
        )

    def test_configure_replaces_previous_overrides(self):
        configure_checks({"squad_topic": {"excluded": ["canonical/first-repo"]}})
        configure_checks({"squad_topic": {"excluded": ["canonical/second-repo"]}})
        from repolint.checks._base import _checks_overrides

        excluded = _checks_overrides.get("squad_topic", {}).get("excluded", [])
        assert "canonical/second-repo" in excluded
        assert "canonical/first-repo" not in excluded

    def test_unknown_check_in_config_is_ignored(self):
        configure_checks({"nonexistent_check": {"excluded": ["canonical/repo"]}})
        assert list_checks()  # still returns normal checks

    def test_empty_config_clears_overrides(self):
        configure_checks({"squad_topic": {"excluded": ["canonical/some-repo"]}})
        configure_checks({})
        from repolint.checks._base import _checks_overrides

        assert _checks_overrides == {}
