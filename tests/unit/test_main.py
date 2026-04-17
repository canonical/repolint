# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.__main__ CLI argument handling."""

import json
import sys
from unittest.mock import patch

import pytest


class TestShowReportFlag:
    def test_show_report_default_path(self, tmp_path, capsys, monkeypatch):
        report = tmp_path / "quality.md"
        report.write_text("# Overview\n\nSome content.\n")
        monkeypatch.setattr(
            sys, "argv", ["repolint", "--output-dir", str(tmp_path), "--show-report"]
        )
        from repolint.__main__ import main

        with patch("repolint.__main__.render_report_in_terminal") as mock_render:
            main()
            mock_render.assert_called_once_with("# Overview\n\nSome content.\n")

    def test_show_report_explicit_path(self, tmp_path, monkeypatch):
        report = tmp_path / "custom.md"
        report.write_text("# Custom\n")
        monkeypatch.setattr(sys, "argv", ["repolint", "--show-report", str(report)])
        from repolint.__main__ import main

        with patch("repolint.__main__.render_report_in_terminal") as mock_render:
            main()
            mock_render.assert_called_once_with("# Custom\n")

    def test_show_report_missing_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--show-report", str(tmp_path / "nonexistent.md")],
        )
        from repolint.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_show_report_skips_analysis(self, tmp_path, monkeypatch):
        report = tmp_path / "quality.md"
        report.write_text("# Report\n")
        monkeypatch.setattr(
            sys, "argv", ["repolint", "--output-dir", str(tmp_path), "--show-report"]
        )
        from repolint.__main__ import main

        with (
            patch("repolint.__main__.render_report_in_terminal"),
            patch("repolint.__main__.analyze") as mock_analyze,
        ):
            main()
            mock_analyze.assert_not_called()


# ---------------------------------------------------------------------------
# Subcheck report generation
# ---------------------------------------------------------------------------

_MINIMAL_QUALITY_DATA = {
    "metadata": {
        "schema": "v0",
        "generated_at": "2026-01-01T00:00:00",
        "checks": [
            {
                "name": "unit_tests",
                "description": "Unit testing best practices.",
                "children": [{"name": "ops_testing", "description": "Doesn't use harness."}],
            }
        ],
    },
    "results": {
        "canonical/my-charm": {
            "ops_testing": {"result": "✅", "message": ""},
            "unit_tests": {"result": "✅", "message": "All subchecks are compliant."},
        }
    },
}


class TestSubcheckReportGeneration:
    def test_subcheck_files_are_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--output-dir", str(tmp_path), "--output", "quality"],
        )
        json_file = tmp_path / "quality.json"
        json_file.write_text(json.dumps(_MINIMAL_QUALITY_DATA))

        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", return_value={}),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
        ):
            main()

        assert (tmp_path / "quality-ops_testing.md").exists()

    def test_subcheck_file_contains_three_sections(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--output-dir", str(tmp_path), "--output", "quality"],
        )
        (tmp_path / "quality.json").write_text(json.dumps(_MINIMAL_QUALITY_DATA))

        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", return_value={}),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
        ):
            main()

        content = (tmp_path / "quality-ops_testing.md").read_text()
        assert "## Failed" in content
        assert "## Passed" in content
        assert "## Excluded" in content


class TestParentCheckReportGeneration:
    def _run_main(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--output-dir", str(tmp_path), "--output", "quality"],
        )
        (tmp_path / "quality.json").write_text(json.dumps(_MINIMAL_QUALITY_DATA))
        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", return_value={}),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
        ):
            main()

    def test_parent_check_file_is_written(self, tmp_path, monkeypatch):
        self._run_main(tmp_path, monkeypatch)
        assert (tmp_path / "quality-unit_tests.md").exists()

    def test_parent_check_file_links_to_subcheck_pages(self, tmp_path, monkeypatch):
        self._run_main(tmp_path, monkeypatch)
        content = (tmp_path / "quality-unit_tests.md").read_text()
        assert "quality-ops_testing.md" in content

    def test_overview_links_to_parent_check_pages(self, tmp_path, monkeypatch):
        self._run_main(tmp_path, monkeypatch)
        overview = (tmp_path / "quality.md").read_text()
        assert "quality-unit_tests.md" in overview
