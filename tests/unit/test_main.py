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
            patch(
                "repolint.__main__.load_config",
                return_value={"repositories": ["canonical/my-charm"]},
            ),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
        ):
            main()

        assert (tmp_path / "quality-ops_testing.md").exists()

    def test_subcheck_file_contains_all_sections(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--output-dir", str(tmp_path), "--output", "quality"],
        )
        (tmp_path / "quality.json").write_text(json.dumps(_MINIMAL_QUALITY_DATA))

        from repolint.__main__ import main

        with (
            patch(
                "repolint.__main__.load_config",
                return_value={"repositories": ["canonical/my-charm"]},
            ),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
        ):
            main()

        content = (tmp_path / "quality-ops_testing.md").read_text()
        assert "## Failed" in content
        assert "## Errored" in content
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
            patch(
                "repolint.__main__.load_config",
                return_value={"repositories": ["canonical/my-charm"]},
            ),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
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


# ---------------------------------------------------------------------------
# Positional repo argument and CWD auto-detection shortcuts
# ---------------------------------------------------------------------------


class TestPositionalRepoArg:
    def _run_main(self, tmp_path, monkeypatch, argv, repos=None):
        monkeypatch.setattr(sys, "argv", argv)
        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=repos or ["canonical/my-charm"],
            ),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
            patch("repolint.__main__._write_reports"),
        ):
            main()

    def test_positional_repo_adds_to_repositories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint", "canonical/my-charm"])
        from repolint.__main__ import main

        captured_config = {}

        def fake_resolve(config, extra_query=None):
            captured_config.update(config)
            return ["canonical/my-charm"]

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.resolve_repositories", side_effect=fake_resolve),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
            patch("repolint.__main__._write_reports"),
        ):
            main()

        assert "canonical/my-charm" in captured_config.get("repositories", [])

    def test_positional_repo_does_not_set_query(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint", "canonical/my-charm"])
        from repolint.__main__ import main

        captured_extra_query = []

        def fake_resolve(config, extra_query=None):
            captured_extra_query.append(extra_query)
            return ["canonical/my-charm"]

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.resolve_repositories", side_effect=fake_resolve),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
            patch("repolint.__main__._write_reports"),
        ):
            main()

        assert captured_extra_query == [None]

    def test_invalid_repo_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint", "notarepo"])
        from repolint.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_repo_and_query_together_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["repolint", "canonical/my-charm", "--query", "org:canonical"]
        )
        from repolint.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_repo_and_show_report_together_exits(self, tmp_path, monkeypatch):
        report = tmp_path / "quality.md"
        report.write_text("# Report\n")
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "canonical/my-charm", "--show-report", str(report)],
        )
        from repolint.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_explicit_missing_config_still_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["repolint", "--config", str(tmp_path / "nonexistent.yaml"), "canonical/my-charm"],
        )
        from repolint.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


class TestCwdAutoDetection:
    def test_cwd_repo_used_when_no_args(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint"])
        from repolint.__main__ import main

        captured_config = {}

        def fake_resolve(config, extra_query=None):
            captured_config.update(config)
            return ["canonical/detected-repo"]

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.get_current_repo", return_value="canonical/detected-repo"),
            patch("repolint.__main__.resolve_repositories", side_effect=fake_resolve),
            patch("repolint.__main__._run_shortcut_mode"),
        ):
            main()

        assert captured_config.get("repositories") == ["canonical/detected-repo"]

    def test_no_cwd_repo_and_no_args_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint"])
        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.get_current_repo", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2

    def test_cwd_not_used_when_query_provided(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["repolint", "--query", "org:canonical"])
        from repolint.__main__ import main

        mock_get_current = patch("repolint.__main__.get_current_repo")

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            mock_get_current as mock_cwd,
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/my-charm"],
            ),
            patch("repolint.__main__._load_quality_data", return_value=_MINIMAL_QUALITY_DATA),
            patch("repolint.__main__._write_reports"),
        ):
            main()

        mock_cwd.assert_not_called()


# ---------------------------------------------------------------------------
# CWD shortcut mode — temp dir and terminal report rendering
# ---------------------------------------------------------------------------

_MINIMAL_QUALITY_DATA_DETECTED = {
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
        "canonical/detected-repo": {
            "ops_testing": {"result": "✅", "message": ""},
            "unit_tests": {"result": "✅", "message": "All subchecks are compliant."},
        }
    },
}


class TestShortcutMode:
    """Tests for the CWD auto-detection shortcut mode."""

    def _run_shortcut(self, monkeypatch, tmp_path, *, render_mock=None):
        """Helper that runs main() in shortcut mode and returns mocked render calls."""
        monkeypatch.setattr(sys, "argv", ["repolint"])
        from repolint.__main__ import main

        render_calls = []

        def capture_render(content):
            render_calls.append(content)

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.get_current_repo", return_value="canonical/detected-repo"),
            patch("repolint.__main__.get_git_toplevel", return_value=tmp_path),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/detected-repo"],
            ),
            patch(
                "repolint.__main__._load_quality_data",
                return_value=_MINIMAL_QUALITY_DATA_DETECTED,
            ),
            patch(
                "repolint.__main__.render_report_in_terminal",
                side_effect=capture_render,
            ),
        ):
            main()

        return render_calls

    def test_shortcut_mode_renders_details_report(self, tmp_path, monkeypatch):
        render_calls = self._run_shortcut(monkeypatch, tmp_path)
        assert len(render_calls) == 1
        assert "canonical/detected-repo" in render_calls[0]

    def test_shortcut_mode_standard_mode_not_triggered(self, tmp_path, monkeypatch):
        """Standard mode (writing to output-dir) must not run in shortcut mode."""
        monkeypatch.setattr(sys, "argv", ["repolint"])
        from repolint.__main__ import main

        with (
            patch("repolint.__main__.load_config", side_effect=FileNotFoundError("no config")),
            patch("repolint.__main__.configure_checks"),
            patch("repolint.__main__.get_current_repo", return_value="canonical/detected-repo"),
            patch("repolint.__main__.get_git_toplevel", return_value=tmp_path),
            patch(
                "repolint.__main__.resolve_repositories",
                return_value=["canonical/detected-repo"],
            ),
            patch(
                "repolint.__main__._load_quality_data",
                return_value=_MINIMAL_QUALITY_DATA_DETECTED,
            ),
            patch("repolint.__main__.render_report_in_terminal"),
            patch("repolint.__main__._run_standard_mode") as mock_std,
        ):
            main()

        mock_std.assert_not_called()


# ---------------------------------------------------------------------------
# Cache merging in _load_quality_data
# ---------------------------------------------------------------------------


class _FakeCheck:
    def __init__(self, name):
        self.name = name


def _write_cache(json_file, results, generated_at="2020-01-01T00:00:00"):
    json_file.write_text(
        json.dumps(
            {
                "metadata": {"schema": "v0", "generated_at": generated_at, "checks": []},
                "results": results,
            }
        )
    )


class TestLoadQualityData:
    def _patches(self, registered_names):
        checks = [_FakeCheck(name) for name in registered_names]
        return (
            patch("repolint.__main__.list_checks", return_value=checks),
            patch("repolint.__main__.build_checks_metadata", return_value=[]),
        )

    def test_reuses_cache_when_complete(self, tmp_path):
        from repolint.__main__ import _load_quality_data

        json_file = tmp_path / "quality.json"
        cached = {"canonical/a": {"c1": {"result": "✅", "message": "ok"}}}
        _write_cache(json_file, cached, generated_at="2020-06-06T00:00:00")

        list_patch, meta_patch = self._patches(["c1"])
        with (
            list_patch,
            meta_patch,
            patch("repolint.__main__.analyze") as mock_analyze,
        ):
            data = _load_quality_data(json_file, ["canonical/a"])

        mock_analyze.assert_not_called()
        assert data["results"]["canonical/a"]["c1"]["message"] == "ok"
        # Timestamp preserved when nothing is re-analyzed.
        assert data["metadata"]["generated_at"] == "2020-06-06T00:00:00"

    def test_analyzes_only_new_repositories(self, tmp_path):
        from repolint.__main__ import _load_quality_data
        from repolint.checks import CheckResult, CheckStatus

        json_file = tmp_path / "quality.json"
        _write_cache(json_file, {"canonical/a": {"c1": {"result": "✅", "message": "cached"}}})

        list_patch, meta_patch = self._patches(["c1"])
        with (
            list_patch,
            meta_patch,
            patch(
                "repolint.__main__.analyze",
                return_value={
                    "canonical/b": {"c1": CheckResult(CheckStatus.NOT_COMPLIANT, "new")}
                },
            ) as mock_analyze,
        ):
            data = _load_quality_data(json_file, ["canonical/a", "canonical/b"])

        mock_analyze.assert_called_once_with(["canonical/b"])
        assert data["results"]["canonical/a"]["c1"]["message"] == "cached"
        assert data["results"]["canonical/b"]["c1"]["result"] == "❌"

    def test_reanalyzes_repo_missing_a_registered_check(self, tmp_path):
        from repolint.__main__ import _load_quality_data
        from repolint.checks import CheckResult, CheckStatus

        json_file = tmp_path / "quality.json"
        # Cache only has c1; a new check c2 was added since.
        _write_cache(json_file, {"canonical/a": {"c1": {"result": "✅", "message": "old"}}})

        list_patch, meta_patch = self._patches(["c1", "c2"])
        with (
            list_patch,
            meta_patch,
            patch(
                "repolint.__main__.analyze",
                return_value={
                    "canonical/a": {
                        "c1": CheckResult(CheckStatus.COMPLIANT, "fresh"),
                        "c2": CheckResult(CheckStatus.COMPLIANT, "fresh"),
                    }
                },
            ) as mock_analyze,
        ):
            data = _load_quality_data(json_file, ["canonical/a"])

        mock_analyze.assert_called_once_with(["canonical/a"])
        assert data["results"]["canonical/a"]["c2"]["message"] == "fresh"

    def test_drops_repositories_no_longer_requested(self, tmp_path):
        from repolint.__main__ import _load_quality_data

        json_file = tmp_path / "quality.json"
        _write_cache(
            json_file,
            {
                "canonical/a": {"c1": {"result": "✅", "message": ""}},
                "canonical/stale": {"c1": {"result": "✅", "message": ""}},
            },
        )

        list_patch, meta_patch = self._patches(["c1"])
        with list_patch, meta_patch, patch("repolint.__main__.analyze") as mock_analyze:
            data = _load_quality_data(json_file, ["canonical/a"])

        mock_analyze.assert_not_called()
        assert set(data["results"]) == {"canonical/a"}

    def test_handles_legacy_flat_cache(self, tmp_path):
        from repolint.__main__ import _load_quality_data

        json_file = tmp_path / "quality.json"
        # Legacy format: bare repo -> results mapping, no metadata wrapper.
        json_file.write_text(json.dumps({"canonical/a": {"c1": {"result": "✅", "message": "x"}}}))

        list_patch, meta_patch = self._patches(["c1"])
        with list_patch, meta_patch, patch("repolint.__main__.analyze") as mock_analyze:
            data = _load_quality_data(json_file, ["canonical/a"])

        mock_analyze.assert_not_called()
        assert data["results"]["canonical/a"]["c1"]["message"] == "x"
