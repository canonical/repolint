# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.utils."""

import subprocess
from unittest.mock import patch

import pytest

from repolint.utils import (
    find_charmcraft_paths,
    find_files_in_path,
    find_regexp_in_path,
    get_repository_details_filename,
    get_repository_slug,
    load_config,
    resolve_repositories,
    sanitize,
    search_repositories_by_query,
)


class TestLoadConfig:
    def test_loads_repositories(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories:\n  - canonical/charm-a\n")
        result = load_config(config)
        assert result["repositories"] == ["canonical/charm-a"]

    def test_loads_repository_query(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repository_query: 'org:canonical topic:platform-engineering'\n")
        result = load_config(config)
        assert result["repository_query"] == "org:canonical topic:platform-engineering"

    def test_repositories_and_query_can_coexist(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text(
            "repositories:\n  - canonical/charm-a\n"
            "repository_query: 'org:canonical topic:platform-engineering'\n"
        )
        result = load_config(config)
        assert result["repositories"] == ["canonical/charm-a"]
        assert "repository_query" in result

    def test_loads_checks_section(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text(
            "repositories:\n  - canonical/charm-a\n"
            "checks:\n  pfe_topic:\n    excluded:\n      - canonical/cbartz-runner-testing\n"
        )
        result = load_config(config)
        assert result["checks"]["pfe_topic"]["excluded"] == ["canonical/cbartz-runner-testing"]

    def test_checks_section_is_optional(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories:\n  - canonical/charm-a\n")
        result = load_config(config)
        assert result.get("checks", {}) == {}

    def test_raises_when_neither_repositories_nor_query(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("something_else:\n  - canonical/charm-a\n")
        with pytest.raises(ValueError, match="repositories"):
            load_config(config)

    def test_raises_when_repositories_not_a_list(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories: canonical/charm-a\n")
        with pytest.raises(ValueError, match="list"):
            load_config(config)

    def test_raises_when_repository_query_not_a_string(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repository_query:\n  - not-a-string\n")
        with pytest.raises(ValueError, match="repository_query"):
            load_config(config)

    def test_raises_when_checks_not_a_mapping(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories:\n  - canonical/charm-a\nchecks: not-a-dict\n")
        with pytest.raises(ValueError, match="checks"):
            load_config(config)

    def test_raises_when_check_config_not_a_mapping(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text(
            "repositories:\n  - canonical/charm-a\nchecks:\n  pfe_topic: not-a-dict\n"
        )
        with pytest.raises(ValueError, match="pfe_topic"):
            load_config(config)

    def test_raises_when_excluded_not_a_list(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text(
            "repositories:\n  - canonical/charm-a\n"
            "checks:\n  pfe_topic:\n    excluded: canonical/bad\n"
        )
        with pytest.raises(ValueError, match="excluded"):
            load_config(config)


class TestSearchRepositoriesByQuery:
    def test_returns_repository_list(self):
        mock_output = "canonical/charm-a\ncanonical/charm-b\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            result = search_repositories_by_query("org:canonical topic:platform-engineering")
        assert result == ["canonical/charm-a", "canonical/charm-b"]

    def test_passes_query_tokens_as_args(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            search_repositories_by_query("org:canonical topic:x topic:y")
        call_args = mock_run.call_args[0][0]
        assert "org:canonical" in call_args
        assert "topic:x" in call_args
        assert "topic:y" in call_args
        assert "archived:false" in call_args

    def test_deduplicates_results(self):
        mock_output = "canonical/charm-a\ncanonical/charm-a\ncanonical/charm-b\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            result = search_repositories_by_query("org:canonical")
        assert result == ["canonical/charm-a", "canonical/charm-b"]

    def test_empty_output_returns_empty_list(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            result = search_repositories_by_query("org:canonical")
        assert result == []

    def test_propagates_called_process_error(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "gh")
            with pytest.raises(subprocess.CalledProcessError):
                search_repositories_by_query("org:canonical")


class TestResolveRepositories:
    def test_returns_config_repositories(self):
        config = {"repositories": ["canonical/charm-a", "canonical/charm-b"]}
        assert resolve_repositories(config) == ["canonical/charm-a", "canonical/charm-b"]

    def test_merges_query_results(self):
        config = {"repositories": ["canonical/charm-a"]}
        with patch("repolint.utils.search_repositories_by_query") as mock_search:
            mock_search.return_value = ["canonical/charm-b", "canonical/charm-c"]
            result = resolve_repositories(config, extra_query="org:canonical")
        assert result == ["canonical/charm-a", "canonical/charm-b", "canonical/charm-c"]

    def test_merges_config_query_and_extra_query(self):
        config = {
            "repositories": ["canonical/charm-a"],
            "repository_query": "org:canonical topic:x",
        }
        with patch("repolint.utils.search_repositories_by_query") as mock_search:
            mock_search.side_effect = [
                ["canonical/charm-b"],  # for config query
                ["canonical/charm-c"],  # for extra query
            ]
            result = resolve_repositories(config, extra_query="org:canonical topic:y")
        assert result == ["canonical/charm-a", "canonical/charm-b", "canonical/charm-c"]

    def test_deduplicates_across_sources(self):
        config = {"repositories": ["canonical/charm-a"]}
        with patch("repolint.utils.search_repositories_by_query") as mock_search:
            mock_search.return_value = ["canonical/charm-a", "canonical/charm-b"]
            result = resolve_repositories(config, extra_query="org:canonical")
        assert result == ["canonical/charm-a", "canonical/charm-b"]

    def test_no_query_skips_search(self):
        config = {"repositories": ["canonical/charm-a"]}
        with patch("repolint.utils.search_repositories_by_query") as mock_search:
            result = resolve_repositories(config)
        mock_search.assert_not_called()
        assert result == ["canonical/charm-a"]

    def test_empty_repositories_with_query_only(self):
        config = {"repository_query": "org:canonical topic:x"}
        with patch("repolint.utils.search_repositories_by_query") as mock_search:
            mock_search.return_value = ["canonical/charm-a"]
            result = resolve_repositories(config)
        assert result == ["canonical/charm-a"]


class TestSanitize:
    def test_replaces_single_quote(self):
        assert sanitize("it's") == "it_s"

    def test_replaces_double_quote(self):
        assert sanitize('say "hello"') == "say _hello_"

    def test_replaces_html_special_chars(self):
        assert sanitize("<script>&</script>") == "_script___/script_"

    def test_plain_text_unchanged(self):
        assert sanitize("hello world") == "hello world"

    def test_empty_string(self):
        assert sanitize("") == ""


class TestGetRepositorySlug:
    def test_replaces_slash(self):
        assert get_repository_slug("canonical/my-charm") == "canonical-my-charm"

    def test_no_slash(self):
        assert get_repository_slug("my-charm") == "my-charm"

    def test_multiple_slashes(self):
        assert get_repository_slug("a/b/c") == "a-b-c"


class TestGetRepositoryDetailsFilename:
    def test_format(self):
        result = get_repository_details_filename("canonical/my-charm")
        assert result == "quality-canonical-my-charm-details.md"

    def test_simple_name(self):
        result = get_repository_details_filename("org/repo")
        assert result == "quality-org-repo-details.md"


class TestFindFilesInPath:
    def test_finds_files(self, tmp_path):
        (tmp_path / "versions.tf").write_text("content")
        (tmp_path / "main.tf").write_text("content")
        result = find_files_in_path(tmp_path, "versions.tf")
        assert len(result) == 1
        assert result[0].name == "versions.tf"

    def test_recursive_search(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "versions.tf").write_text("content")
        result = find_files_in_path(tmp_path, "versions.tf")
        assert len(result) == 1

    def test_nonexistent_path_returns_empty(self, tmp_path):
        result = find_files_in_path(tmp_path / "nonexistent", "versions.tf")
        assert result == []

    def test_path_is_file_returns_empty(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        result = find_files_in_path(f, "file.txt")
        assert result == []


class TestFindRegexpInPath:
    def test_finds_pattern_in_file(self, tmp_path):
        (tmp_path / "config.yaml").write_text("use-canonical-k8s: true\n")
        assert find_regexp_in_path(tmp_path, "use-canonical-k8s: true") is True

    def test_returns_false_when_not_found(self, tmp_path):
        (tmp_path / "config.yaml").write_text("something else\n")
        assert find_regexp_in_path(tmp_path, "use-canonical-k8s: true") is False

    def test_multiline_pattern(self, tmp_path):
        (tmp_path / "config.yaml").write_text("key:\n  value: true\n")
        assert find_regexp_in_path(tmp_path, r"key:.*value: true") is True

    def test_nonexistent_path_returns_false(self, tmp_path):
        assert find_regexp_in_path(tmp_path / "nonexistent", "pattern") is False

    def test_skips_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("secret-pattern")
        assert find_regexp_in_path(git_dir, "secret-pattern") is False

    def test_recursive_finds_in_subdir(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "file.py").write_text("import jubilant\n")
        assert find_regexp_in_path(tmp_path, "import jubilant", recursive=True) is True

    def test_non_recursive_does_not_descend(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "file.py").write_text("import jubilant\n")
        assert find_regexp_in_path(tmp_path, "import jubilant", recursive=False) is False


class TestFindCharmcraftPaths:
    def test_finds_charmcraft_yaml(self, tmp_path):
        (tmp_path / "charmcraft.yaml").write_text("type: charm\n")
        result = find_charmcraft_paths(tmp_path)
        assert len(result) == 1
        assert result[0].name == "charmcraft.yaml"

    def test_excludes_charmcraft_in_tests_dir(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "charmcraft.yaml").write_text("type: charm\n")
        result = find_charmcraft_paths(tmp_path)
        assert result == []

    def test_finds_multiple_charms(self, tmp_path):
        for name in ["charm-a", "charm-b"]:
            charm_dir = tmp_path / name
            charm_dir.mkdir()
            (charm_dir / "charmcraft.yaml").write_text("type: charm\n")
        result = find_charmcraft_paths(tmp_path)
        assert len(result) == 2
