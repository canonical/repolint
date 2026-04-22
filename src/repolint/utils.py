# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions for repository file-system and GitHub operations."""

import re
import subprocess
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

import yaml

from repolint.config import TMP_DIR

# Mapping from repo name (owner/repo) to a local directory that should be used
# instead of cloning.  Populated via :func:`local_repo_override`.
_local_overrides: dict[str, Path] = {}


def sanitize(text: str) -> str:
    """Sanitize text for use in HTML attributes."""
    return text.translate(str.maketrans("'\"<>&", "_____"))


def get_repository_slug(repo: str) -> str:
    """Return a filesystem-safe slug for a repository (replace / with -)."""
    return repo.replace("/", "-")


def get_repository_details_filename(repo: str) -> str:
    """Return the filename of the detailed markdown report for a repository."""
    return f"{get_repository_slug(repo)}-details.md"


@contextmanager
def local_repo_override(repo: str, path: Path) -> Generator[None, None, None]:
    """Context manager that makes :func:`clone_repository_locally` return *path* for *repo*.

    The override is active only for the duration of the ``with`` block and is
    always removed on exit, even if an exception occurs.  This keeps the module
    state clean across test runs and multiple calls to ``main()``.
    """
    _local_overrides[repo] = path
    try:
        yield
    finally:
        _local_overrides.pop(repo, None)


def get_git_toplevel() -> Path | None:
    """Return the top-level directory of the current git repository, or *None*.

    Runs ``git rev-parse --show-toplevel`` so the returned path is always the
    repository root, regardless of which subdirectory the process started in.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _validate_repositories(data: dict, config_path: Path) -> None:
    repos = data.get("repositories", [])
    if not isinstance(repos, list):
        raise ValueError(f"'repositories' in {config_path} must be a list.")
    invalid = [r for r in repos if not isinstance(r, str) or "/" not in r]
    if invalid:
        raise ValueError(
            f"Invalid repository entries in {config_path} (expected 'org/repo'): {invalid}"
        )
    query = data.get("repository_query")
    if query is not None and not isinstance(query, str):
        raise ValueError(f"'repository_query' in {config_path} must be a string.")


def _validate_checks(data: dict, config_path: Path) -> None:
    checks = data.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError(f"'checks' in {config_path} must be a mapping.")
    for check_name, check_cfg in checks.items():
        if not isinstance(check_cfg, dict):
            raise ValueError(f"'checks.{check_name}' in {config_path} must be a mapping.")
        excluded = check_cfg.get("excluded", [])
        if not isinstance(excluded, list):
            raise ValueError(f"'checks.{check_name}.excluded' in {config_path} must be a list.")
        patterns = check_cfg.get("patterns", [])
        if not isinstance(patterns, list):
            raise ValueError(f"'checks.{check_name}.patterns' in {config_path} must be a list.")
        for i, p in enumerate(patterns):
            if not isinstance(p, str):
                raise ValueError(
                    f"'checks.{check_name}.patterns[{i}]' in {config_path} must be a string."
                )


def load_config(config_path: Path) -> dict:
    """Load and validate a repolint YAML config file, returning the parsed dict.

    The config file must contain at least one of:

    - a ``repositories`` key with a list of ``org/repo`` strings, or
    - a ``repository_query`` key with a GitHub search query string.

    Both keys may be present; their results are merged by
    :func:`resolve_repositories`.

    An optional ``checks`` key may provide per-check configuration, e.g. to
    configure topic patterns or add extra exclusions::

        checks:
          github_topics:
            patterns:
              - "^squad-"
              - "^product-"
          github2jira:
            excluded:
              - canonical/some-repo
    """
    try:
        with config_path.open() as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Create a repolint.yaml with a 'repositories' list or 'repository_query'."
        )
    if not isinstance(data, dict):
        raise ValueError(f"Config file {config_path} must be a YAML mapping.")
    if "repositories" not in data and "repository_query" not in data:
        raise ValueError(
            f"Config file {config_path} must contain at least one of "
            "'repositories' or 'repository_query'."
        )
    _validate_repositories(data, config_path)
    _validate_checks(data, config_path)
    return data


def search_repositories_by_query(query: str) -> list[str]:
    """Search GitHub for repositories matching *query* and return ``org/repo`` names.

    *query* is a GitHub repository search query string, for example::

        "org:canonical topic:platform-engineering topic:squad-emea"

    The query string is split on whitespace; each token becomes a positional
    argument to ``gh search repos``.  ``archived:false`` is always appended to
    exclude archived repositories.  Results are returned in the order GitHub
    returns them, deduplicated.

    Raises :exc:`subprocess.CalledProcessError` if the ``gh`` CLI fails.
    """
    cmd = [
        "gh",
        "search",
        "repos",
        *query.split(),
        "archived:false",
        "--json",
        "fullName",
        "--jq",
        ".[].fullName",
        "--limit",
        "1000",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    return list(dict.fromkeys(line for line in lines if line))


def resolve_repositories(config: dict, extra_query: str | None = None) -> list[str]:
    """Return the deduplicated list of repositories to analyse.

    Sources, merged in this order (duplicates removed, preserving first occurrence):

    1. ``config["repositories"]`` — static list from the config file.
    2. Results of ``config["repository_query"]`` — if present.
    3. Results of *extra_query* — if provided (e.g. from the CLI ``--query`` flag).
    """
    repos: list[str] = list(config.get("repositories", []))
    for query in filter(None, [config.get("repository_query"), extra_query]):
        repos.extend(search_repositories_by_query(query))
    # Deduplicate while preserving order.
    return list(dict.fromkeys(repos))


@lru_cache(maxsize=200)
def get_repository_topics(repo: str) -> list[str]:
    """Fetch the topics of a repository using GitHub CLI."""
    cmd = [
        "gh",
        "repo",
        "view",
        repo,
        "--json",
        "repositoryTopics",
        "--jq",
        ".repositoryTopics[].name",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    return []


def clone_repository_locally(repo: str) -> Path:
    """Clone the repository locally (shallow) and return its path.

    If a local override has been registered via :func:`local_repo_override`,
    that path is returned directly without cloning.
    """
    if repo in _local_overrides:
        return _local_overrides[repo]
    local_path = TMP_DIR / repo.replace("/", "_")
    if not local_path.exists():
        subprocess.run(
            ["gh", "repo", "clone", repo, str(local_path), "--", "--depth", "1"],  # noqa: S607
            check=True,
        )
    return local_path


def get_current_repo() -> str | None:
    """Return the GitHub ``org/repo`` for the current working directory, or *None*.

    Reads the ``origin`` remote URL from git and extracts the repository name.
    Returns *None* if the CWD is not a git repository, has no ``origin`` remote,
    or the origin does not point to github.com.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    url = result.stdout.strip()
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not match:
        return None
    repo = match.group(1)
    # Validate exactly owner/repo (two non-empty segments).
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return repo


@lru_cache(maxsize=50)
def _get_git_tracked_files(path: Path) -> frozenset[Path] | None:
    """Return the set of git-tracked files under *path*, or *None*.

    Runs ``git ls-files`` with *path* as the working directory.  Returns a
    ``frozenset`` of absolute :class:`~pathlib.Path` objects so callers can do
    O(1) membership tests.  Returns *None* when *path* is not inside a git
    repository or ``git`` is not available, allowing callers to fall back to
    unfiltered scanning.

    Results are cached per directory (up to 50 entries) to avoid repeated
    subprocess calls when multiple checks scan the same repository.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=path,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None
    return frozenset(path / entry for entry in result.stdout.splitlines() if entry)


def find_charmcraft_paths(path: Path) -> list[Path]:
    """Find all charmcraft.yaml files in path, excluding test directories."""
    tracked = _get_git_tracked_files(path)
    charmcraft_files = list(path.rglob("charmcraft.yaml"))
    if tracked is not None:
        charmcraft_files = [f for f in charmcraft_files if f in tracked]
    return [f for f in charmcraft_files if "tests" not in str(f.parent)]


def find_files_in_path(path: Path, filename: str) -> list[Path]:
    """Find all files with a specific name under the given directory."""
    if not (path.exists() and path.is_dir()):
        return []
    tracked = _get_git_tracked_files(path)
    found_files = []
    for file in path.rglob(filename):
        if file.is_file() and (tracked is None or file in tracked):
            found_files.append(file)
    return found_files


def find_regexp_in_path(path: Path, pattern: str, *, recursive: bool = False) -> bool:
    """Search for a regexp pattern in all files under path.

    Note: file contents are read in full so patterns can span multiple lines
    (re.DOTALL is enabled).  Git-tracked files only are scanned when the path
    is inside a git repository; otherwise all files are scanned (excluding
    hidden ``.git`` directories).
    """
    if not (path.exists() and path.is_dir()):
        return False
    tracked = _get_git_tracked_files(path)
    glob = path.rglob("*") if recursive else path.glob("*")
    for file in glob:
        if not file.is_file():
            continue
        if tracked is not None:
            if file not in tracked:
                continue
        elif ".git" in file.parts:
            continue
        try:
            content = file.read_text()
        except UnicodeDecodeError:
            print(f"WARNING: couldn't decode {file}, skipping.")
            continue
        if re.search(pattern, content, re.DOTALL):
            return True
    return False
