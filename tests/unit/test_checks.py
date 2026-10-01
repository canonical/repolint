# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.checks — Check base class and registry."""

from unittest.mock import patch

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

    def test_excluded_repo_returns_excluded(self):
        check = _make_simple_check("_test_excl_a")
        configure_checks({"_test_excl_a": {"excluded": ["canonical/excluded-repo"]}})
        result = check("canonical/excluded-repo")
        assert result.result == CheckStatus.EXCLUDED

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

    def test_dependency_errored_propagates_error(self):
        check = _make_simple_check("_test_dep_err")
        check.depends_on = ["dep_check"]  # type: ignore[assignment]
        previous = {"dep_check": CheckResult(CheckStatus.ERROR, "boom")}
        result = check("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.ERROR
        assert "dep_check" in result.message

    def test_missing_dependency_raises(self):
        check = _make_simple_check("_test_dep_c")
        check.depends_on = ["missing_dep"]  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="missing_dep"):
            check("canonical/some-repo", previous_results={})

    def test_run_subprocess_failure_returns_error(self):
        import subprocess

        class _FailingCheck(Check):
            name = "_test_fail"  # type: ignore[assignment]
            description = "test"
            parent = ""

            def run(self, repo: str) -> CheckResult:
                raise subprocess.CalledProcessError(1, ["gh", "repo", "clone"])

        check = _REGISTRY.pop("_test_fail")
        result = check("canonical/some-repo")
        assert result.result == CheckStatus.ERROR
        assert "could not run" in result.message.lower()


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

    def test_one_child_errored_returns_error(self):
        parent = ParentCheck("_test_parent_err")
        self._added.append("_test_parent_err")
        self._register_child("_child_err1", "_test_parent_err", CheckStatus.COMPLIANT)
        self._register_child("_child_err2", "_test_parent_err", CheckStatus.ERROR)
        previous = {
            "_child_err1": CheckResult(CheckStatus.COMPLIANT, ""),
            "_child_err2": CheckResult(CheckStatus.ERROR, "could not run"),
        }
        result = parent("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.ERROR
        assert "_child_err2" in result.message

    def test_failure_takes_precedence_over_error(self):
        parent = ParentCheck("_test_parent_mix")
        self._added.append("_test_parent_mix")
        self._register_child("_child_mix1", "_test_parent_mix", CheckStatus.NOT_COMPLIANT)
        self._register_child("_child_mix2", "_test_parent_mix", CheckStatus.ERROR)
        previous = {
            "_child_mix1": CheckResult(CheckStatus.NOT_COMPLIANT, "failed"),
            "_child_mix2": CheckResult(CheckStatus.ERROR, "could not run"),
        }
        result = parent("canonical/some-repo", previous_results=previous)
        assert result.result == CheckStatus.NOT_COMPLIANT

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

    def test_all_leaf_checks_have_valid_parent(self):
        """Every leaf check must declare a parent that is either '_internal' or a registered ParentCheck."""
        parent_names = {c.name for c in list_checks() if isinstance(c, ParentCheck)}
        valid_parents = parent_names | {"_internal"}
        invalid = [
            c.name
            for c in list_checks()
            if not isinstance(c, ParentCheck) and c.parent not in valid_parents
        ]
        assert not invalid, f"Leaf checks with unregistered parent: {invalid}"


# ---------------------------------------------------------------------------
# GithubTopicsCheck
# ---------------------------------------------------------------------------


class TestGithubTopicsCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _get_check(self):
        check = get_check("github_topics")
        assert check is not None
        return check

    def test_no_patterns_returns_compliant(self):
        """With no patterns configured the check passes unconditionally."""
        configure_checks({"github_topics": {"patterns": []}})
        with patch(
            "repolint.checks.github_topics.get_repository_topics", return_value=["squad-emea"]
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_matching_pattern_returns_compliant(self):
        configure_checks({"github_topics": {"patterns": ["^squad-"]}})
        with patch(
            "repolint.checks.github_topics.get_repository_topics",
            return_value=["squad-emea", "charm"],
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_missing_pattern_returns_not_compliant(self):
        configure_checks({"github_topics": {"patterns": ["^squad-", "^product-"]}})
        with patch(
            "repolint.checks.github_topics.get_repository_topics",
            return_value=["squad-emea"],  # no product-* topic
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "^product-" in result.message

    def test_all_patterns_must_match(self):
        configure_checks({"github_topics": {"patterns": ["^squad-", "^product-", "^charm$"]}})
        with patch(
            "repolint.checks.github_topics.get_repository_topics",
            return_value=["squad-emea", "product-openstack"],
            # missing 'charm' topic
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "^charm$" in result.message

    def test_no_config_returns_compliant(self):
        """With no github_topics config at all, the check passes."""
        configure_checks({})
        with patch("repolint.checks.github_topics.get_repository_topics", return_value=[]):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT


# ---------------------------------------------------------------------------
# GithubRequiredChecksCheck
# ---------------------------------------------------------------------------


class TestGithubRequiredChecksCheck:
    def _get_check(self):
        check = get_check("github_required_checks")
        assert check is not None
        return check

    def test_required_checks_present_returns_compliant(self):
        with (
            patch(
                "repolint.checks.github_required_checks.get_default_branch", return_value="main"
            ),
            patch(
                "repolint.checks.github_required_checks.get_required_status_checks",
                return_value=["ci/tests", "lint"],
            ),
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT
        assert "2" in result.message

    def test_no_branch_protection_returns_not_compliant(self):
        with (
            patch(
                "repolint.checks.github_required_checks.get_default_branch", return_value="main"
            ),
            patch(
                "repolint.checks.github_required_checks.get_required_status_checks",
                return_value=None,
            ),
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "main" in result.message

    def test_protection_without_checks_returns_not_compliant(self):
        with (
            patch(
                "repolint.checks.github_required_checks.get_default_branch", return_value="main"
            ),
            patch(
                "repolint.checks.github_required_checks.get_required_status_checks",
                return_value=[],
            ),
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "main" in result.message

    def test_permission_denied_returns_error(self):
        from repolint.checks.github_required_checks import BranchProtectionPermissionError

        with (
            patch(
                "repolint.checks.github_required_checks.get_default_branch", return_value="main"
            ),
            patch(
                "repolint.checks.github_required_checks.get_required_status_checks",
                side_effect=BranchProtectionPermissionError(
                    "Insufficient permissions to read branch protection for 'main'."
                ),
            ),
        ):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.ERROR
        assert "permission" in result.message.lower()

    def test_check_has_github_parent(self):
        check = self._get_check()
        assert check.parent == "github"


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
        instance = get_check("github_topics")
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
        configure_checks({"github2jira": {"excluded": ["canonical/extra-repo"]}})
        check = get_check("github2jira")
        assert check is not None
        result = check("canonical/extra-repo")
        assert result.result == CheckStatus.EXCLUDED

    def test_configure_non_excluded_repo_runs(self):
        configure_checks({"github2jira": {"excluded": ["canonical/excluded-repo"]}})
        check = get_check("github2jira")
        assert check is not None
        from repolint.checks._base import _checks_overrides

        assert "canonical/excluded-repo" in _checks_overrides.get("github2jira", {}).get(
            "excluded", []
        )
        assert "canonical/allowed-repo" not in _checks_overrides.get("github2jira", {}).get(
            "excluded", []
        )

    def test_configure_replaces_previous_overrides(self):
        configure_checks({"github2jira": {"excluded": ["canonical/first-repo"]}})
        configure_checks({"github2jira": {"excluded": ["canonical/second-repo"]}})
        from repolint.checks._base import _checks_overrides

        excluded = _checks_overrides.get("github2jira", {}).get("excluded", [])
        assert "canonical/second-repo" in excluded
        assert "canonical/first-repo" not in excluded

    def test_unknown_check_in_config_is_ignored(self):
        configure_checks({"nonexistent_check": {"excluded": ["canonical/repo"]}})
        assert list_checks()  # still returns normal checks

    def test_empty_config_clears_overrides(self):
        configure_checks({"github2jira": {"excluded": ["canonical/some-repo"]}})
        configure_checks({})
        from repolint.checks._base import _checks_overrides

        assert _checks_overrides == {}


# ---------------------------------------------------------------------------
# UseGhRunnersCheck
# ---------------------------------------------------------------------------

_OPERATOR_WORKFLOWS_LINE = "uses: canonical/operator-workflows/.github/workflows/test.yaml"


class TestUseGhRunnersCheck:
    def _make_workflows_dir(self, tmp_path):
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        return workflows

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.use_gh_runners.clone_repository_locally",
            return_value=tmp_path,
        )

    def test_no_workflows_dir_returns_not_eligible(self, tmp_path):
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.NOT_ELIGIBLE

    def test_no_matching_workflow_returns_not_eligible(self, tmp_path):
        workflows = self._make_workflows_dir(tmp_path)
        (workflows / "ci.yaml").write_text("name: ci\n")
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.NOT_ELIGIBLE

    def test_matching_workflow_no_self_hosted_runner_returns_compliant(self, tmp_path):
        workflows = self._make_workflows_dir(tmp_path)
        (workflows / "test.yaml").write_text(
            f"name: test\njobs:\n  unit:\n    {_OPERATOR_WORKFLOWS_LINE}\n"
        )
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_matching_workflow_self_hosted_runner_false_returns_compliant(self, tmp_path):
        workflows = self._make_workflows_dir(tmp_path)
        (workflows / "test.yaml").write_text(
            f"name: test\njobs:\n  unit:\n    {_OPERATOR_WORKFLOWS_LINE}\n"
            "    with:\n      self-hosted-runner: false\n"
        )
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_matching_workflow_self_hosted_runner_true_returns_not_compliant(self, tmp_path):
        workflows = self._make_workflows_dir(tmp_path)
        (workflows / "test.yaml").write_text(
            f"name: test\njobs:\n  unit:\n    {_OPERATOR_WORKFLOWS_LINE}\n"
            "    with:\n      self-hosted-runner: true\n"
        )
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "test.yaml" in result.message

    def test_multiple_workflows_one_offending_returns_not_compliant(self, tmp_path):
        workflows = self._make_workflows_dir(tmp_path)
        (workflows / "ok.yaml").write_text(
            f"name: ok\njobs:\n  unit:\n    {_OPERATOR_WORKFLOWS_LINE}\n"
        )
        (workflows / "bad.yaml").write_text(
            f"name: bad\njobs:\n  unit:\n    {_OPERATOR_WORKFLOWS_LINE}\n"
            "    with:\n      self-hosted-runner: true\n"
        )
        with self._patch_clone(tmp_path):
            from repolint.checks.use_gh_runners import UseGhRunnersCheck

            result = UseGhRunnersCheck().run("canonical/some-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "bad.yaml" in result.message
        assert "ok.yaml" not in result.message

    def test_check_has_unit_tests_parent(self):
        check = get_check("use_gh_runners")
        assert check is not None
        assert check.parent == "unit_tests"


# ---------------------------------------------------------------------------
# GithubCodeownersCheck
# ---------------------------------------------------------------------------


class TestGithubCodeownersCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.github_codeowners.clone_repository_locally",
            return_value=tmp_path,
        )

    def _get_check(self):
        from repolint.checks.github_codeowners import GithubCodeownersCheck

        return GithubCodeownersCheck()

    def test_missing_codeowners_returns_not_compliant(self, tmp_path):
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "CODEOWNERS" in result.message

    def test_root_codeowners_no_patterns_returns_compliant(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("* @canonical/my-team\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_github_dir_codeowners_is_found(self, tmp_path):
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        (github_dir / "CODEOWNERS").write_text("* @canonical/my-team\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_docs_dir_codeowners_is_found(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "CODEOWNERS").write_text("* @canonical/my-team\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_valid_pattern_matches_returns_compliant(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("# comment\n* @canonical/my-team\n")
        configure_checks({"codeowners": {"valid_patterns": [r"@canonical/my-team$"]}})
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_valid_pattern_missing_returns_not_compliant(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("* @canonical/my-team\n")
        configure_checks({"codeowners": {"valid_patterns": [r"@canonical/other-team$"]}})
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "@canonical/other-team$" in result.message

    def test_any_valid_pattern_matching_returns_compliant(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("* @canonical/my-team\n")
        configure_checks(
            {"codeowners": {"valid_patterns": [r"@canonical/other-team$", r"@canonical/my-team$"]}}
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_invalid_pattern_matched_returns_not_compliant(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("* @some-individual\n")
        configure_checks({"codeowners": {"invalid_patterns": [r"@some-individual"]}})
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "@some-individual" in result.message

    def test_comment_and_blank_lines_are_ignored_for_matching(self, tmp_path):
        (tmp_path / "CODEOWNERS").write_text("# @canonical/ignored-team\n\n* @canonical/my-team\n")
        configure_checks({"codeowners": {"invalid_patterns": [r"@canonical/ignored-team"]}})
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_excluded_repo_returns_excluded(self, tmp_path):
        configure_checks({"codeowners": {"excluded": ["canonical/my-charm"]}})
        with self._patch_clone(tmp_path):
            result = self._get_check()("canonical/my-charm")
        assert result.result == CheckStatus.EXCLUDED

    def test_check_has_github_parent(self):
        check = get_check("codeowners")
        assert check is not None
        assert check.parent == "github"


# ---------------------------------------------------------------------------
# SupportedBasesCheck
# ---------------------------------------------------------------------------


class TestSupportedBasesCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.supported_bases.clone_repository_locally",
            return_value=tmp_path,
        )

    def _get_check(self):
        from repolint.checks.supported_bases import SupportedBasesCheck

        return SupportedBasesCheck()

    def _write_charmcraft(self, tmp_path, content, subdir=None):
        directory = tmp_path / subdir if subdir else tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "charmcraft.yaml").write_text(content)

    def test_platforms_with_target_base_returns_compliant(self, tmp_path):
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@26.04:amd64:\n    build-on: [ubuntu@26.04:amd64]\n",
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_platforms_missing_target_base_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@24.04:amd64:\n    build-on: [ubuntu@24.04:amd64]\n",
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "26.04" in result.message

    def test_legacy_bases_key_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(
            tmp_path,
            'type: charm\nbases:\n  - build-on:\n      - name: ubuntu\n        channel: "24.04"\n',
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "deprecated" in result.message

    def test_missing_platforms_key_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT

    def test_multiple_charms_all_must_be_compliant(self, tmp_path):
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@26.04:amd64: {}\n",
            subdir="charm-a",
        )
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@24.04:amd64: {}\n",
            subdir="charm-b",
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "charm-b" in result.message

    def test_multiple_charms_all_compliant_returns_compliant(self, tmp_path):
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@26.04:amd64: {}\n",
            subdir="charm-a",
        )
        self._write_charmcraft(
            tmp_path,
            "type: charm\nplatforms:\n  ubuntu@26.04:amd64: {}\n",
            subdir="charm-b",
        )
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_malformed_yaml_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\nplatforms: [unterminated\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "could not parse" in result.message

    def test_no_charms_returns_compliant(self, tmp_path):
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_check_has_charmhub_parent(self):
        check = get_check("supported_bases")
        assert check is not None
        assert check.parent == "dependencies"

    def test_depends_on_actively_maintained(self):
        check = get_check("supported_bases")
        assert check is not None
        assert "actively_maintained" in check.depends_on


# ---------------------------------------------------------------------------
# ActivelyMaintainedCheck
# ---------------------------------------------------------------------------


class TestRootlessCharmCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.rootless_charm.clone_repository_locally",
            return_value=tmp_path,
        )

    def _get_check(self):
        from repolint.checks.rootless_charm import RootlessCharmCheck

        return RootlessCharmCheck()

    def _write_charmcraft(self, tmp_path, content, subdir=None):
        directory = tmp_path / subdir if subdir else tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "charmcraft.yaml").write_text(content)

    def test_non_root_charm_user_returns_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: sudoer\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_root_charm_user_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: root\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "root" in result.message

    def test_missing_charm_user_key_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "missing" in result.message

    def test_malformed_yaml_returns_not_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: [unterminated\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "could not parse" in result.message

    def test_multiple_charms_all_must_be_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: sudoer\n", subdir="charm-a")
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: root\n", subdir="charm-b")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "charm-b" in result.message

    def test_multiple_charms_all_compliant_returns_compliant(self, tmp_path):
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: sudoer\n", subdir="charm-a")
        self._write_charmcraft(tmp_path, "type: charm\ncharm-user: sudoer\n", subdir="charm-b")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_no_charms_returns_compliant(self, tmp_path):
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_check_has_security_parent(self):
        check = get_check("rootless_charm")
        assert check is not None
        assert check.parent == "security"

    def test_depends_on_contains_charm(self):
        check = get_check("rootless_charm")
        assert check is not None
        assert "contains_charm" in check.depends_on

    def test_not_eligible_when_contains_charm_not_compliant(self):
        check = get_check("rootless_charm")
        assert check is not None
        previous_results = {
            "contains_charm": CheckResult(CheckStatus.NOT_COMPLIANT, "No charms found."),
        }
        result = check("canonical/my-repo", previous_results)
        assert result.result == CheckStatus.NOT_ELIGIBLE


class TestContainsRockCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.contains_rock.clone_repository_locally",
            return_value=tmp_path,
        )

    def _get_check(self):
        from repolint.checks.contains_rock import ContainsRockCheck

        return ContainsRockCheck()

    def _write_rockcraft(self, tmp_path, content, subdir=None):
        directory = tmp_path / subdir if subdir else tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "rockcraft.yaml").write_text(content)

    def test_no_rocks_returns_not_compliant(self, tmp_path):
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT

    def test_rock_present_returns_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: my-rock\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-rock")
        assert result.result == CheckStatus.COMPLIANT

    def test_check_has_internal_parent(self):
        check = get_check("contains_rock")
        assert check is not None
        assert check.parent == "_internal"


class TestRootlessRockCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _patch_clone(self, tmp_path):
        return patch(
            "repolint.checks.rootless_rock.clone_repository_locally",
            return_value=tmp_path,
        )

    def _get_check(self):
        from repolint.checks.rootless_rock import RootlessRockCheck

        return RootlessRockCheck()

    def _write_rockcraft(self, tmp_path, content, subdir=None):
        directory = tmp_path / subdir if subdir else tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "rockcraft.yaml").write_text(content)

    def test_non_root_run_user_returns_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: my-rock\nrun-user: _daemon_\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-rock")
        assert result.result == CheckStatus.COMPLIANT

    def test_root_run_user_returns_not_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: my-rock\nrun-user: root\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-rock")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "root" in result.message

    def test_missing_run_user_key_returns_not_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: my-rock\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-rock")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "missing" in result.message

    def test_malformed_yaml_returns_not_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: my-rock\nrun-user: [unterminated\n")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-rock")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "could not parse" in result.message

    def test_multiple_rocks_all_must_be_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: rock-a\nrun-user: _daemon_\n", subdir="rock-a")
        self._write_rockcraft(tmp_path, "name: rock-b\nrun-user: root\n", subdir="rock-b")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "rock-b" in result.message

    def test_multiple_rocks_all_compliant_returns_compliant(self, tmp_path):
        self._write_rockcraft(tmp_path, "name: rock-a\nrun-user: _daemon_\n", subdir="rock-a")
        self._write_rockcraft(tmp_path, "name: rock-b\nrun-user: _daemon_\n", subdir="rock-b")
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_no_rocks_returns_compliant(self, tmp_path):
        with self._patch_clone(tmp_path):
            result = self._get_check().run("canonical/my-repo")
        assert result.result == CheckStatus.COMPLIANT

    def test_check_has_security_parent(self):
        check = get_check("rootless_rock")
        assert check is not None
        assert check.parent == "security"

    def test_depends_on_contains_rock(self):
        check = get_check("rootless_rock")
        assert check is not None
        assert "contains_rock" in check.depends_on

    def test_not_eligible_when_contains_rock_not_compliant(self):
        check = get_check("rootless_rock")
        assert check is not None
        previous_results = {
            "contains_rock": CheckResult(CheckStatus.NOT_COMPLIANT, "No rocks found."),
        }
        result = check("canonical/my-repo", previous_results)
        assert result.result == CheckStatus.NOT_ELIGIBLE


class TestActivelyMaintainedCheck:
    def setup_method(self):
        configure_checks({})

    def teardown_method(self):
        configure_checks({})

    def _get_check(self):
        from repolint.checks.actively_maintained import ActivelyMaintainedCheck

        return ActivelyMaintainedCheck()

    def _patch_topics(self, topics):
        return patch(
            "repolint.checks.actively_maintained.get_repository_topics",
            return_value=topics,
        )

    def test_no_maintenance_topic_returns_compliant(self):
        with self._patch_topics(["squad-emea", "platform-engineering"]):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_no_topics_returns_compliant(self):
        with self._patch_topics([]):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.COMPLIANT

    def test_maintenance_topic_returns_not_compliant(self):
        with self._patch_topics(["maintenance-mode"]):
            result = self._get_check().run("canonical/my-charm")
        assert result.result == CheckStatus.NOT_COMPLIANT
        assert "maintenance-mode" in result.message

    def test_check_is_internal(self):
        check = get_check("actively_maintained")
        assert check is not None
        assert check.parent == "_internal"
