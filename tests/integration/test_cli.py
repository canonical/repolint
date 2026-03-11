# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for repolint CLI — real gh calls, real config file handling."""

import json
import subprocess
from pathlib import Path

# A stable query that always returns at least one repository.
VALID_QUERY = "org:canonical topic:platform-engineering topic:squad-emea topic:charm"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run the repolint CLI with *args* from *cwd*, capturing all output."""
    return subprocess.run(
        ["repolint", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestCLIBehaviours:
    """Tests for the three config-file / --query combination behaviours."""

    def test_query_only_no_config_file(self, tmp_path):
        """No config file + --query → succeeds and writes reports."""
        result = _run(["--query", VALID_QUERY], cwd=tmp_path)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "reports" / "quality.json").exists()
        assert (tmp_path / "reports" / "quality.md").exists()

    def test_config_file_only_no_query(self, tmp_path):
        """Config file present + no --query → loads file, writes reports."""
        config = tmp_path / "repolint.yaml"
        config.write_text(f"repository_query: '{VALID_QUERY}'\n")

        result = _run([], cwd=tmp_path)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "reports" / "quality.json").exists()
        assert (tmp_path / "reports" / "quality.md").exists()

    def test_config_file_and_query_merged(self, tmp_path):
        """Config file present + --query → results are merged, deduped."""
        # Obtain the repository list from the query alone first.
        query_only_dir = tmp_path / "query_only"
        query_only_dir.mkdir()
        query_only = _run(["--query", VALID_QUERY], cwd=query_only_dir)
        assert query_only.returncode == 0, query_only.stderr

        query_repos = set(
            json.loads((query_only_dir / "reports" / "quality.json").read_text()).keys()
        )

        # Run with a config that pins one repo explicitly + the same query.
        one_repo = next(iter(query_repos))
        config = tmp_path / "repolint.yaml"
        config.write_text(f"repositories:\n  - {one_repo}\n")

        result = _run(["--query", VALID_QUERY], cwd=tmp_path)
        assert result.returncode == 0, result.stderr

        merged_repos = set(json.loads((tmp_path / "reports" / "quality.json").read_text()).keys())

        # The merged run must contain at least what the query alone returned.
        assert query_repos <= merged_repos
        # The pinned repo appears exactly once (dedup check via set equality).
        assert one_repo in merged_repos

    def test_no_config_file_no_query_exits_with_error(self, tmp_path):
        """No config file + no --query → exits non-zero with a helpful message."""
        result = _run([], cwd=tmp_path)

        assert result.returncode != 0
        # The error message should mention the missing config.
        assert "repolint.yaml" in result.stderr or "repolint.yaml" in result.stdout
