# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.report."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from repolint.checks import CheckResult
from repolint.config import CheckStatus
from repolint.report import (
    analyze,
    analyze_repo,
    render_markdown_details,
    render_markdown_overview,
)


def _mock_check(name, description="desc", hidden=False, aggregates=None):
    return SimpleNamespace(
        name=name, description=description, hidden=hidden, aggregates=aggregates or []
    )


# ---------------------------------------------------------------------------
# render_markdown_details
# ---------------------------------------------------------------------------


class TestRenderMarkdownDetails:
    def test_includes_repo_name_as_heading(self):
        results = {
            "pfe_topic": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        md = render_markdown_details("canonical/my-charm", results)
        assert "# canonical/my-charm" in md

    def test_includes_criterion_name_and_result(self):
        results = {
            "pfe_topic": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        md = render_markdown_details("canonical/my-charm", results)
        assert "pfe_topic" in md
        assert CheckStatus.COMPLIANT in md

    def test_includes_message_when_present(self):
        results = {
            "pfe_topic": CheckResult(CheckStatus.NOT_COMPLIANT, "No topic found."),
        }
        md = render_markdown_details("canonical/my-charm", results)
        assert "No topic found." in md

    def test_skips_unknown_criterion(self):
        results = {
            "unknown_criterion_xyz": CheckResult(CheckStatus.COMPLIANT, ""),
        }
        md = render_markdown_details("canonical/my-charm", results)
        # Should not raise and should still produce heading
        assert "# canonical/my-charm" in md

    def test_aggregate_label_shown(self):
        results = {
            "github": CheckResult(CheckStatus.COMPLIANT, "All subchecks are compliant."),
        }
        md = render_markdown_details("canonical/my-charm", results)
        assert "(aggregate)" in md


# ---------------------------------------------------------------------------
# render_markdown_overview
# ---------------------------------------------------------------------------


class TestRenderMarkdownOverview:
    def test_table_has_header_and_separator(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch("repolint.report.get_repository_details_filename", return_value="details.md"),
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
            patch("repolint.report.get_repository_details_filename", return_value="details.md"),
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
            patch("repolint.report.get_repository_details_filename", return_value="details.md"),
        ):
            mock_lc.return_value = [_mock_check("check_b", description="Second check")]
            results: dict = {
                "canonical/my-charm": {}  # no check_b entry
            }
            with pytest.raises(RuntimeError, match="check_b"):
                render_markdown_overview(results)

    def test_hidden_criteria_excluded_from_headers(self):
        with (
            patch("repolint.report.list_checks") as mock_lc,
            patch("repolint.report.get_repository_details_filename", return_value="details.md"),
        ):
            mock_lc.return_value = [
                _mock_check("hidden_check", description="Hidden", hidden=True),
                _mock_check("visible_check", description="Visible"),
            ]
            results = {
                "canonical/my-charm": {
                    "hidden_check": CheckResult(CheckStatus.COMPLIANT, ""),
                    "visible_check": CheckResult(CheckStatus.COMPLIANT, ""),
                }
            }
            md = render_markdown_overview(results)

        assert "visible_check" in md
        assert "hidden_check" not in md


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
