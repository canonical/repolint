# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.__main__ CLI argument handling."""

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
