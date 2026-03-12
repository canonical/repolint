# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.report."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from repolint.checks import CheckResult, list_checks
from repolint.config import CheckStatus
from repolint.report import (
    analyze,
    analyze_repo,
    render_markdown_details,
    render_markdown_overview,
    render_report_in_terminal,
)


def _mock_check(name, description="desc", parent=""):
    return SimpleNamespace(name=name, description=description, parent=parent)


# ---------------------------------------------------------------------------
# render_markdown_details
# ---------------------------------------------------------------------------


class TestRenderMarkdownDetails:
    def test_includes_repo_name_as_heading(self):
        md = render_markdown_details("canonical/my-charm", {})
        assert "# canonical/my-charm" in md

    def test_shows_parent_and_child_checks(self):
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [
                _mock_check("github_topics", parent="github"),
                _mock_check("github", parent=""),
            ]
            results = {
                "github": CheckResult(CheckStatus.COMPLIANT, "All subchecks are compliant."),
                "github_topics": CheckResult(CheckStatus.COMPLIANT, ""),
            }
            md = render_markdown_details("canonical/my-charm", results)
        assert "github" in md
        assert "github_topics" in md
        assert CheckStatus.COMPLIANT in md

    def test_leaf_check_nested_under_parent(self):
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [
                _mock_check("github_topics", parent="github"),
                _mock_check("github", parent=""),
            ]
            results = {
                "github": CheckResult(CheckStatus.COMPLIANT, ""),
                "github_topics": CheckResult(
                    CheckStatus.NOT_COMPLIANT, "No topic matches pattern."
                ),
            }
            md = render_markdown_details("canonical/my-charm", results)
        lines = md.splitlines()
        github_line = next(
            i for i, ln in enumerate(lines) if "github" in ln and "github_topics" not in ln
        )
        topics_line = next(i for i, ln in enumerate(lines) if "github_topics" in ln)
        assert topics_line > github_line
        assert lines[topics_line].startswith("  "), "Child check should be indented"
        assert "No topic matches pattern." in md

    def test_message_appended_inline(self):
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [
                _mock_check("github_topics", parent="github"),
                _mock_check("github", parent=""),
            ]
            results = {
                "github": CheckResult(CheckStatus.NOT_COMPLIANT, "Subcheck(s) failing."),
                "github_topics": CheckResult(CheckStatus.NOT_COMPLIANT, "No topic matches."),
            }
            md = render_markdown_details("canonical/my-charm", results)
        assert "Subcheck(s) failing." in md
        assert "No topic matches." in md

    def test_unknown_criterion_in_results_ignored(self):
        """Entries in results that are not in list_checks() are simply not rendered."""
        results = {"unknown_criterion_xyz": CheckResult(CheckStatus.COMPLIANT, "")}
        md = render_markdown_details("canonical/my-charm", results)
        assert "# canonical/my-charm" in md
        assert "unknown_criterion_xyz" not in md

    def test_github_topics_nested_under_github_real_registry(self):
        """Using the real check registry, github_topics must appear nested under github."""
        results = {c.name: CheckResult(CheckStatus.COMPLIANT, "") for c in list_checks()}
        md = render_markdown_details("canonical/my-charm", results)
        lines = md.splitlines()
        github_line = next(
            i
            for i, ln in enumerate(lines)
            if ln.startswith("- ") and "github" in ln and "github_topics" not in ln
        )
        topics_line = next(i for i, ln in enumerate(lines) if "github_topics" in ln)
        assert topics_line > github_line, "github_topics must appear after github parent"
        assert lines[topics_line].startswith("  "), "github_topics must be indented under github"

    def test_internal_group_rendered_with_real_registry(self):
        """_internal group and its children appear in the detailed report."""
        results = {c.name: CheckResult(CheckStatus.COMPLIANT, "") for c in list_checks()}
        md = render_markdown_details("canonical/my-charm", results)
        lines = md.splitlines()
        internal_line = next((i for i, ln in enumerate(lines) if ln == "- _internal"), None)
        assert internal_line is not None, "_internal group must be present"
        child_lines = [ln for ln in lines[internal_line + 1 :] if ln.startswith("  - ")]
        assert any("contains_charm" in ln for ln in child_lines)
        assert any("contains_k8s_charm" in ln for ln in child_lines)

    def test_unregistered_parent_group_rendered(self):
        """Checks with an unregistered parent appear under a group bullet."""
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [
                _mock_check("helper_a", parent="helpers"),
                _mock_check("helper_b", parent="helpers"),
            ]
            results = {
                "helper_a": CheckResult(CheckStatus.COMPLIANT, "ok"),
                "helper_b": CheckResult(CheckStatus.NOT_COMPLIANT, "fail"),
            }
            md = render_markdown_details("canonical/my-charm", results)
        lines = md.splitlines()
        group_line = next((i for i, ln in enumerate(lines) if ln == "- helpers"), None)
        assert group_line is not None, "group bullet must be present"
        assert any("helper_a" in ln for ln in lines[group_line + 1 :])
        assert any("helper_b" in ln for ln in lines[group_line + 1 :])


# ---------------------------------------------------------------------------
# render_markdown_overview
# ---------------------------------------------------------------------------


class TestRenderMarkdownOverview:
    def test_table_has_header_and_separator(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch(
                "repolint.report.get_repository_details_filename",
                return_value="details.md",
            ),
        ):
            mock_lc.return_value = [_mock_check("check_b", description="Second check")]
            results = {
                "canonical/repo-a": {
                    "check_b": CheckResult(CheckStatus.COMPLIANT, ""),
                }
            }
            md = render_markdown_overview(results)

        lines = md.splitlines()
        assert lines[0].startswith("|")
        assert "---" in lines[1]

    def test_repo_link_present(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch(
                "repolint.report.get_repository_details_filename",
                return_value="details.md",
            ),
        ):
            mock_lc.return_value = [_mock_check("check_b", description="Second check")]
            results = {
                "canonical/my-charm": {
                    "check_b": CheckResult(CheckStatus.COMPLIANT, ""),
                }
            }
            md = render_markdown_overview(results)

        assert "canonical/my-charm" in md
        assert "https://github.com/canonical/my-charm" in md

    def test_missing_criterion_result_raises(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch(
                "repolint.report.get_repository_details_filename",
                return_value="details.md",
            ),
        ):
            mock_lc.return_value = [_mock_check("check_b", description="Second check", parent="")]
            results: dict = {"canonical/my-charm": {}}  # no check_b entry
            with pytest.raises(RuntimeError, match="check_b"):
                render_markdown_overview(results)

    def test_leaf_checks_excluded_from_headers(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch(
                "repolint.report.get_repository_details_filename",
                return_value="details.md",
            ),
        ):
            mock_lc.return_value = [
                _mock_check("parent_check", description="Parent", parent=""),
                _mock_check("leaf_check", description="Leaf", parent="parent_check"),
            ]
            results = {
                "canonical/my-charm": {
                    "parent_check": CheckResult(CheckStatus.COMPLIANT, ""),
                    "leaf_check": CheckResult(CheckStatus.COMPLIANT, ""),
                }
            }
            md = render_markdown_overview(results)

        assert "parent_check" in md
        assert "leaf_check" not in md


# ---------------------------------------------------------------------------
# analyze_repo
# ---------------------------------------------------------------------------


class TestAnalyzeRepo:
    def test_runs_all_checks(self):
        from unittest.mock import MagicMock

        mock_check_a = MagicMock()
        mock_check_a.name = "check_a"
        mock_check_a.return_value = CheckResult(CheckStatus.COMPLIANT, "ok")
        mock_check_b = MagicMock()
        mock_check_b.name = "check_b"
        mock_check_b.return_value = CheckResult(CheckStatus.COMPLIANT, "ok")
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [mock_check_a, mock_check_b]
            results = analyze_repo("canonical/test-repo")

        assert "check_a" in results
        assert "check_b" in results

    def test_results_keyed_by_check_name(self):
        from unittest.mock import MagicMock

        mock_check_a = MagicMock()
        mock_check_a.name = "check_a"
        mock_check_a.return_value = CheckResult(CheckStatus.COMPLIANT, "ok")
        with patch("repolint.report.list_checks") as mock_lc:
            mock_lc.return_value = [mock_check_a]
            results = analyze_repo("canonical/test-repo")

        assert results["check_a"].result == CheckStatus.COMPLIANT

    def test_all_registered_checks_in_results(self, tmp_path):
        """analyze_repo must return a result keyed by every check in list_checks()."""
        # Minimal charm repo structure so contains_charm returns COMPLIANT
        (tmp_path / "charmcraft.yaml").write_text("name: test\n")
        (tmp_path / ".github").mkdir()

        expected_names = {c.name for c in list_checks()}

        with (
            patch("repolint.checks.github_topics.get_repository_topics", return_value=[]),
            patch(
                "repolint.checks.contains_charm.clone_repository_locally", return_value=tmp_path
            ),
            patch(
                "repolint.checks.contains_k8s_charm.clone_repository_locally",
                return_value=tmp_path,
            ),
            patch("repolint.checks.github2jira.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.ops_testing.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.juju4.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.ck8s.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.jubilant.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.tf_v1.clone_repository_locally", return_value=tmp_path),
            patch("repolint.checks.charmlibs.clone_repository_locally", return_value=tmp_path),
        ):
            results = analyze_repo("canonical/my-charm")

        assert set(results.keys()) == expected_names
        assert "github_topics" in results


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_returns_results_for_all_repos(self):
        repos = ["canonical/repo-a", "canonical/repo-b"]
        with patch("repolint.report.analyze_repo") as mock_ar:
            mock_ar.return_value = {"check_a": CheckResult(CheckStatus.COMPLIANT, "")}
            results = analyze(repos)
        assert set(results.keys()) == set(repos)

    def test_repos_are_sorted(self):
        repos = ["canonical/z-repo", "canonical/a-repo"]
        with patch("repolint.report.analyze_repo") as mock_ar:
            mock_ar.return_value = {}
            results = analyze(repos)
        assert list(results.keys()) == ["canonical/a-repo", "canonical/z-repo"]


# ---------------------------------------------------------------------------
# render_report_in_terminal
# ---------------------------------------------------------------------------


class TestRenderReportInTerminal:
    def test_strips_span_tags(self, capsys):
        content = "# Title\n\n<span title='tooltip'>check_name</span>: ✅\n"
        render_report_in_terminal(content)
        captured = capsys.readouterr()
        assert "check_name" in captured.out
        assert "<span" not in captured.out
        assert "tooltip" not in captured.out

    def test_renders_heading(self, capsys):
        render_report_in_terminal("# My Report\n")
        captured = capsys.readouterr()
        assert "My Report" in captured.out

    def test_plain_markdown_unchanged(self, capsys):
        render_report_in_terminal("- item one\n- item two\n")
        captured = capsys.readouterr()
        assert "item one" in captured.out
        assert "item two" in captured.out

    def test_nested_spans_unwrapped(self, capsys):
        content = "<span title='outer'><span title='inner'>text</span></span>\n"
        render_report_in_terminal(content)
        captured = capsys.readouterr()
        assert "text" in captured.out
        assert "<span" not in captured.out
