# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.report."""

from unittest.mock import patch

import pytest

from repolint.checks import CheckResult, build_checks_metadata, list_checks
from repolint.config import CheckStatus
from repolint.report import (
    analyze,
    analyze_repo,
    render_markdown_details,
    render_markdown_overview,
    render_markdown_parent_check,
    render_markdown_subcheck,
    render_report_in_terminal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_quality_data(
    checks_meta: list[dict],
    repo_results: dict,
    repo: str = "canonical/my-charm",
) -> dict:
    """Build a minimal quality_data dict for use in render function tests."""
    return {
        "metadata": {"schema": "v0", "generated_at": "2026-01-01T00:00:00", "checks": checks_meta},
        "results": {repo: repo_results},
    }


def _result_dict(status: CheckStatus, message: str = "") -> dict:
    return {"result": status.value, "message": message}


# ---------------------------------------------------------------------------
# render_markdown_details
# ---------------------------------------------------------------------------


class TestRenderMarkdownDetails:
    def test_includes_repo_name_as_heading(self):
        quality_data = _make_quality_data([], {})
        md = render_markdown_details("canonical/my-charm", quality_data)
        assert "# canonical/my-charm" in md

    def test_shows_parent_and_child_checks(self):
        checks_meta = [
            {
                "name": "github",
                "description": "GitHub checks",
                "children": [{"name": "github_topics", "description": "Topics check"}],
            }
        ]
        repo_results = {
            "github": _result_dict(CheckStatus.COMPLIANT, "All subchecks are compliant."),
            "github_topics": _result_dict(CheckStatus.COMPLIANT),
        }
        md = render_markdown_details(
            "canonical/my-charm", _make_quality_data(checks_meta, repo_results)
        )
        assert "github" in md
        assert "github_topics" in md
        assert CheckStatus.COMPLIANT in md

    def test_leaf_check_nested_under_parent(self):
        checks_meta = [
            {
                "name": "github",
                "description": "desc",
                "children": [{"name": "github_topics", "description": "topics"}],
            }
        ]
        repo_results = {
            "github": _result_dict(CheckStatus.COMPLIANT),
            "github_topics": _result_dict(CheckStatus.NOT_COMPLIANT, "No topic matches pattern."),
        }
        md = render_markdown_details(
            "canonical/my-charm", _make_quality_data(checks_meta, repo_results)
        )
        lines = md.splitlines()
        github_line = next(
            i for i, ln in enumerate(lines) if "github" in ln and "github_topics" not in ln
        )
        topics_line = next(i for i, ln in enumerate(lines) if "github_topics" in ln)
        assert topics_line > github_line
        assert lines[topics_line].startswith("  "), "Child check should be indented"
        assert "No topic matches pattern." in md

    def test_message_appended_inline(self):
        checks_meta = [
            {
                "name": "github",
                "description": "desc",
                "children": [{"name": "github_topics", "description": "topics"}],
            }
        ]
        repo_results = {
            "github": _result_dict(CheckStatus.NOT_COMPLIANT, "Subcheck(s) failing."),
            "github_topics": _result_dict(CheckStatus.NOT_COMPLIANT, "No topic matches."),
        }
        md = render_markdown_details(
            "canonical/my-charm", _make_quality_data(checks_meta, repo_results)
        )
        assert "Subcheck(s) failing." in md
        assert "No topic matches." in md

    def test_unknown_criterion_in_results_ignored(self):
        """Results not referenced in metadata checks are not rendered."""
        checks_meta: list[dict] = []
        repo_results = {"unknown_criterion_xyz": _result_dict(CheckStatus.COMPLIANT)}
        md = render_markdown_details(
            "canonical/my-charm", _make_quality_data(checks_meta, repo_results)
        )
        assert "# canonical/my-charm" in md
        assert "unknown_criterion_xyz" not in md

    def test_github_topics_nested_under_github_real_registry(self):
        """Using the real check registry, github_topics must appear nested under github."""
        all_checks = list_checks()
        results = {c.name: _result_dict(CheckStatus.COMPLIANT) for c in all_checks}
        quality_data = {
            "metadata": {"schema": "v0", "generated_at": None, "checks": build_checks_metadata()},
            "results": {"canonical/my-charm": results},
        }
        md = render_markdown_details("canonical/my-charm", quality_data)
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
        all_checks = list_checks()
        results = {c.name: _result_dict(CheckStatus.COMPLIANT) for c in all_checks}
        quality_data = {
            "metadata": {"schema": "v0", "generated_at": None, "checks": build_checks_metadata()},
            "results": {"canonical/my-charm": results},
        }
        md = render_markdown_details("canonical/my-charm", quality_data)
        lines = md.splitlines()
        internal_line = next((i for i, ln in enumerate(lines) if ln == "- _internal"), None)
        assert internal_line is not None, "_internal group must be present"
        child_lines = [ln for ln in lines[internal_line + 1 :] if ln.startswith("  - ")]
        assert any("contains_charm" in ln for ln in child_lines)
        assert any("contains_k8s_charm" in ln for ln in child_lines)

    def test_unregistered_parent_group_rendered(self):
        """Checks with an unregistered parent appear under a group bullet."""
        checks_meta = [
            {
                "name": "helpers",
                "description": None,
                "children": [
                    {"name": "helper_a", "description": "a"},
                    {"name": "helper_b", "description": "b"},
                ],
            }
        ]
        repo_results = {
            "helper_a": _result_dict(CheckStatus.COMPLIANT, "ok"),
            "helper_b": _result_dict(CheckStatus.NOT_COMPLIANT, "fail"),
        }
        md = render_markdown_details(
            "canonical/my-charm", _make_quality_data(checks_meta, repo_results)
        )
        lines = md.splitlines()
        group_line = next((i for i, ln in enumerate(lines) if ln == "- helpers"), None)
        assert group_line is not None, "group bullet must be present"
        assert any("helper_a" in ln for ln in lines[group_line + 1 :])
        assert any("helper_b" in ln for ln in lines[group_line + 1 :])


# ---------------------------------------------------------------------------
# render_markdown_overview
# ---------------------------------------------------------------------------


class TestRenderMarkdownOverview:
    def _make_overview_data(self, checks_meta, repo_results_map, details_file="details.md"):
        return {
            "metadata": {
                "schema": "v0",
                "generated_at": "2026-01-01T00:00:00",
                "checks": checks_meta,
            },
            "results": repo_results_map,
        }

    def test_table_has_header_and_separator(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [{"name": "check_b", "description": "Second check", "children": []}]
            quality_data = self._make_overview_data(
                checks_meta,
                {"canonical/repo-a": {"check_b": _result_dict(CheckStatus.COMPLIANT)}},
            )
            md = render_markdown_overview(quality_data)

        lines = md.splitlines()
        assert lines[0].startswith("|")
        assert "---" in lines[1]

    def test_repo_link_present(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [{"name": "check_b", "description": "Second check", "children": []}]
            quality_data = self._make_overview_data(
                checks_meta,
                {"canonical/my-charm": {"check_b": _result_dict(CheckStatus.COMPLIANT)}},
            )
            md = render_markdown_overview(quality_data)

        assert "canonical/my-charm" in md
        assert "https://github.com/canonical/my-charm" in md

    def test_missing_criterion_result_raises(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [{"name": "check_b", "description": "Second check", "children": []}]
            quality_data = self._make_overview_data(
                checks_meta,
                {"canonical/my-charm": {}},  # no check_b entry
            )
            with pytest.raises(RuntimeError, match="check_b"):
                render_markdown_overview(quality_data)

    def test_leaf_checks_excluded_from_headers(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [
                {
                    "name": "parent_check",
                    "description": "Parent",
                    "children": [{"name": "leaf_check", "description": "Leaf"}],
                }
            ]
            quality_data = self._make_overview_data(
                checks_meta,
                {
                    "canonical/my-charm": {
                        "parent_check": _result_dict(CheckStatus.COMPLIANT),
                        "leaf_check": _result_dict(CheckStatus.COMPLIANT),
                    }
                },
            )
            md = render_markdown_overview(quality_data)

        assert "parent_check" in md
        assert "leaf_check" not in md

    def test_overview_without_output_has_no_links_in_headers(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [{"name": "unit_tests", "description": "Unit tests", "children": []}]
            quality_data = self._make_overview_data(
                checks_meta,
                {"canonical/my-charm": {"unit_tests": _result_dict(CheckStatus.COMPLIANT)}},
            )
            md = render_markdown_overview(quality_data)

        header_line = md.splitlines()[0]
        assert "unit_tests" in header_line
        assert "unit_tests.md" not in header_line

    def test_overview_with_output_links_headers_to_parent_pages(self):
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="details.md",
        ):
            checks_meta = [{"name": "unit_tests", "description": "Unit tests", "children": []}]
            quality_data = self._make_overview_data(
                checks_meta,
                {"canonical/my-charm": {"unit_tests": _result_dict(CheckStatus.COMPLIANT)}},
            )
            md = render_markdown_overview(quality_data, output="quality")

        header_line = md.splitlines()[0]
        assert "quality-unit_tests.md" in header_line


# ---------------------------------------------------------------------------
# render_markdown_parent_check
# ---------------------------------------------------------------------------


class TestRenderMarkdownParentCheck:
    def _make_data(self, repo_results_map: dict) -> dict:
        return {
            "metadata": {"schema": "v0", "generated_at": "2026-01-01T00:00:00", "checks": []},
            "results": repo_results_map,
        }

    def test_heading_contains_parent_name_and_description(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        children = [{"name": "ops_testing", "description": "Doesn't use harness."}]
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_parent_check(
                "unit_tests", "Unit testing.", children, data, "quality"
            )
        assert "# unit_tests" in md
        assert "Unit testing." in md

    def test_subcheck_columns_link_to_subcheck_pages(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        children = [{"name": "ops_testing", "description": "Doesn't use harness."}]
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_parent_check(
                "unit_tests", "Unit testing.", children, data, "quality"
            )
        assert "quality-ops_testing.md" in md

    def test_table_contains_all_repos(self):
        data = self._make_data(
            {
                "canonical/charm-a": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)},
                "canonical/charm-b": {
                    "ops_testing": _result_dict(CheckStatus.NOT_COMPLIANT, "harness found")
                },
            }
        )
        children = [{"name": "ops_testing", "description": ""}]
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_parent_check("unit_tests", "", children, data, "quality")
        assert "canonical/charm-a" in md
        assert "canonical/charm-b" in md

    def test_table_has_header_and_separator(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        children = [{"name": "ops_testing", "description": ""}]
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_parent_check("unit_tests", "", children, data, "quality")
        table_lines = [ln for ln in md.splitlines() if ln.startswith("|")]
        assert len(table_lines) >= 2
        assert "---" in table_lines[1]

    def test_repo_link_and_magnifier_present(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        children = [{"name": "ops_testing", "description": ""}]
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="canonical-my-charm-details.md",
        ):
            md = render_markdown_parent_check("unit_tests", "", children, data, "quality")
        assert "https://github.com/canonical/my-charm" in md
        assert "🔍" in md
        assert "canonical-my-charm-details.md" in md

    def test_missing_subcheck_result_renders_empty_cell(self):
        data = self._make_data({"canonical/my-charm": {}})  # no ops_testing result
        children = [{"name": "ops_testing", "description": ""}]
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_parent_check("unit_tests", "", children, data, "quality")
        # Row should still appear; empty cell is allowed
        assert "canonical/my-charm" in md


class TestRenderMarkdownSubcheck:
    def _make_data(self, repo_results_map: dict) -> dict:
        return {
            "metadata": {"schema": "v0", "generated_at": "2026-01-01T00:00:00", "checks": []},
            "results": repo_results_map,
        }

    def test_heading_contains_subcheck_name_and_description(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        md = render_markdown_subcheck("ops_testing", "Repository doesn't use harness.", data)
        assert "# ops_testing" in md
        assert "Repository doesn't use harness." in md

    def test_heading_no_description(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        md = render_markdown_subcheck("ops_testing", "", data)
        assert md.startswith("# ops_testing\n")
        assert " — " not in md.splitlines()[0]

    def test_failed_section_contains_non_compliant_repos(self):
        data = self._make_data(
            {
                "canonical/bad-charm": {
                    "ops_testing": _result_dict(CheckStatus.NOT_COMPLIANT, "Found harness.")
                },
                "canonical/good-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)},
            }
        )
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_subcheck("ops_testing", "", data)
        failed_section = md.split("## Failed")[1].split("##")[0]
        passed_section = md.split("## Passed")[1].split("##")[0]
        assert "canonical/bad-charm" in failed_section
        assert "canonical/good-charm" not in failed_section
        assert "canonical/good-charm" in passed_section

    def test_excluded_section_contains_not_eligible_repos(self):
        data = self._make_data(
            {
                "canonical/skipped": {
                    "ops_testing": _result_dict(CheckStatus.NOT_ELIGIBLE, "Not a charm.")
                }
            }
        )
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_subcheck("ops_testing", "", data)
        excluded_section = md.split("## Excluded")[1]
        assert "canonical/skipped" in excluded_section

    def test_empty_section_shows_none_placeholder(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_subcheck("ops_testing", "", data)
        failed_section = md.split("## Failed")[1].split("##")[0]
        assert "_None._" in failed_section

    def test_table_has_repo_link_and_magnifier(self):
        data = self._make_data(
            {"canonical/my-charm": {"ops_testing": _result_dict(CheckStatus.COMPLIANT)}}
        )
        with patch(
            "repolint.report.get_repository_details_filename",
            return_value="canonical-my-charm-details.md",
        ):
            md = render_markdown_subcheck("ops_testing", "", data)
        assert "https://github.com/canonical/my-charm" in md
        assert "🔍" in md
        assert "canonical-my-charm-details.md" in md

    def test_repo_not_in_subcheck_skipped(self):
        """Repos that have no result for the subcheck are silently skipped."""
        data = self._make_data(
            {
                "canonical/my-charm": {"other_check": _result_dict(CheckStatus.COMPLIANT)},
            }
        )
        with patch("repolint.report.get_repository_details_filename", return_value="details.md"):
            md = render_markdown_subcheck("ops_testing", "", data)
        assert "canonical/my-charm" not in md

    def test_all_three_section_headers_present(self):
        data = self._make_data({})
        md = render_markdown_subcheck("ops_testing", "", data)
        assert "## Failed" in md
        assert "## Passed" in md
        assert "## Excluded" in md


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
