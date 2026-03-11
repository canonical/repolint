# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.utils."""

import pytest

from repolint.utils import (
    find_charmcraft_paths,
    find_files_in_path,
    find_regexp_in_path,
    get_repository_details_filename,
    get_repository_slug,
    load_repositories,
    sanitize,
)


class TestLoadRepositories:
    def test_loads_valid_config(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories:\n  - canonical/charm-a\n  - canonical/charm-b\n")
        result = load_repositories(config)
        assert result == ["canonical/charm-a", "canonical/charm-b"]

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match=r"repolint\.yaml"):
            load_repositories(tmp_path / "repolint.yaml")

    def test_raises_when_repositories_key_missing(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("something_else:\n  - canonical/charm-a\n")
        with pytest.raises(ValueError, match="repositories"):
            load_repositories(config)

    def test_raises_when_repositories_not_a_list(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories: canonical/charm-a\n")
        with pytest.raises(ValueError, match="list"):
            load_repositories(config)

    def test_raises_on_invalid_repo_format(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories:\n  - not-a-valid-repo\n")
        with pytest.raises(ValueError, match="not-a-valid-repo"):
            load_repositories(config)

    def test_empty_repositories_list(self, tmp_path):
        config = tmp_path / "repolint.yaml"
        config.write_text("repositories: []\n")
        assert load_repositories(config) == []


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
