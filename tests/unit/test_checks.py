# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.checks — Check base class and registry."""

import pytest

from repolint.checks import Check, CheckResult, ParentCheck, get_check, list_checks
from repolint.checks._base import _REGISTRY, configure_checks
from repolint.config import CheckStatus

# ---------------------------------------------------------------------------
# Helpers — minimal concrete Check subclasses for testing cross-cutting logic
# ---------------------------------------------------------------------------


def _make_simple_check(check_name: str, result: CheckStatus = CheckStatus.COMPLIANT) -> Check:
    """Dynamically create a minimal Check subclass with a fixed run() result."""

    class _SimpleCheck(Check):
        name = check_name  # type: ignore[assignment]
        description = "test"
        parent = ""

        def run(self, repo: str) -> CheckResult:
            return CheckResult(result, "ran")

    # Remove from registry so test helpers don't pollute other tests.
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
# ParentCheck — dynamic child discovery
# ---------------------------------------------------------------------------


class TestParentCheck:
    def setup_method(self):
        # Clean up any test keys we add
        self._added: list[str] = []

    def teardown_method(self):
        for key in self._added:
            _REGISTRY.pop(key, None)

    def _register_child(self, name: str, parent_name: str, result: CheckStatus) -> Check:
        """Create and manually register a child check."""

        class _ChildCheck(Check):
            def run(self, repo):
                return CheckResult(result, "ran")

        _ChildCheck.name = name  # type: ignore[attr-defined]
        _ChildCheck.description = "test"  # type: ignore[attr-defined]
        _ChildCheck.parent = parent_name  # type: ignore[attr-defined]
        _ChildCheck.depends_on = []  # type: ignore[attr-defined]

        instance = object.__new__(_ChildCheck)
        _REGISTRY[name] = instance
        self._added.append(name)
        return instance

    def test_all_children_compliant_returns_compliant(self):
        parent = ParentCheck("_test_parent_a")
        self._added.append("_test_parent_a")
        self._register_child("_child_a1", "_test_parent_a", CheckStatus.COMPLIANT)
        self._register_child("_child_a2", "_test_parent_a", CheckStatus.COMPLIANT)
        previous = {
            "_child_a1": CheckResult(CheckStatus.COMPLIANT, ""),
            "_child_a2": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        result = parent("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.COMPLIANT

    def test_one_child_failing_returns_not_compliant(self):
        parent = ParentCheck("_test_parent_b")
        self._added.append("_test_parent_b")
        self._register_child("_child_b1", "_test_parent_b", CheckStatus.COMPLIANT)
        self._register_child("_child_b2", "_test_parent_b", CheckStatus.NOT_COMPLIANT)
        previous = {
            "_child_b1": CheckResult(CheckStatus.COMPLIANT, ""),
            "_child_b2": CheckResult(CheckStatus.NOT_COMPLIANT, "failed"),
        }
        result = parent("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "_child_b2" in result.message

    def test_missing_child_result_raises(self):
        parent = ParentCheck("_test_parent_c")
        self._added.append("_test_parent_c")
        self._register_child("_child_c1", "_test_parent_c", CheckStatus.COMPLIANT)
        with pytest.raises(RuntimeError):
            parent("canonical/some-repo", previous_results={})


# ---------------------------------------------------------------------------
# Check.description — class attribute
# ---------------------------------------------------------------------------


class TestCheckDescription:
    def test_description_is_class_attribute(self):
        class _DescCheck(Check):
            name = "_test_desc_a"  # type: ignore[assignment]
            description = "A test description."
            parent = ""

            def run(self, repo: str) -> CheckResult:
                return CheckResult(CheckStatus.COMPLIANT, "")

        check = _REGISTRY.pop("_test_desc_a")
        assert check.description == "A test description."

    def test_leaf_checks_have_non_empty_description(self):
        """Every check registered in the package must have a non-empty description."""
        for check in list_checks():
            assert isinstance(check.description, str), f"{check.name}.description is not a str"
            assert check.description, f"{check.name}.description is empty"


# ---------------------------------------------------------------------------
# __init_subclass__ enforcement
# ---------------------------------------------------------------------------


class TestInitSubclassEnforcement:
    def test_missing_description_raises_type_error(self):
        with pytest.raises(TypeError, match="description"):

            class _BadCheck(Check):
                name = "_test_bad_no_desc"  # type: ignore[assignment]
                parent = ""

                def run(self, repo):
                    return CheckResult(CheckStatus.COMPLIANT, "")

            _REGISTRY.pop("_test_bad_no_desc", None)

    def test_missing_parent_raises_type_error(self):
        with pytest.raises(TypeError, match="parent"):

            class _BadCheck2(Check):
                name = "_test_bad_no_parent"  # type: ignore[assignment]
                description = "desc"

                def run(self, repo):
                    return CheckResult(CheckStatus.COMPLIANT, "")

            _REGISTRY.pop("_test_bad_no_parent", None)


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
        """Every check (leaf and parent) must have a registered Check instance."""
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

    def test_children_appear_before_parents(self):
        seen: set[str] = set()
        for check in list_checks():
            if isinstance(check, ParentCheck):
                # All children of this parent must have appeared before it
                children = [c for c in list_checks() if c.parent == check.name]
                for child in children:
                    assert child.name in seen, (
                        f"Child {child.name!r} has not appeared before parent {check.name!r}"
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
