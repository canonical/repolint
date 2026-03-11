# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions for repository file-system and GitHub operations."""

import re
import subprocess
from functools import lru_cache
from pathlib import Path

from repolint.config import CONFIG_PATH, TMP_DIR


def sanitize(text: str) -> str:
    """Sanitize text for use in HTML attributes."""
    return text.translate(str.maketrans("'\"<>&", "_____"))


def get_repository_slug(repo: str) -> str:
    """Return a filesystem-safe slug for a repository (replace / with -)."""
    return repo.replace("/", "-")


def get_repository_details_filename(repo: str) -> str:
    """Return the filename of the detailed markdown report for a repository."""
    return f"quality-{get_repository_slug(repo)}-details.md"


def list_repositories(squad: str) -> list[str]:
    """List repositories to analyze for a given squad or 'all'."""
    if squad == "all":
        repo_file = CONFIG_PATH / "repos.txt"
    else:
        repo_file = CONFIG_PATH / f"squad-repos.{squad}.txt"
    return repo_file.read_text().splitlines()


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
    """Clone the repository locally (shallow) and return its path."""
    local_path = Path(TMP_DIR) / repo.replace("/", "_")
    if not local_path.exists():
        subprocess.run(
            ["gh", "repo", "clone", repo, str(local_path), "--", "--depth", "1"],  # noqa: S607
            check=True,
        )
    return local_path


def find_charmcraft_paths(path: Path) -> list[Path]:
    """Find all charmcraft.yaml files in path, excluding test directories."""
    charmcraft_files = list(path.rglob("charmcraft.yaml"))
    return [f for f in charmcraft_files if "tests" not in str(f.parent)]


def find_files_in_path(path: Path, filename: str) -> list[Path]:
    """Find all files with a specific name under the given directory."""
    found_files = []
    if path.exists() and path.is_dir():
        for file in path.rglob(filename):
            if file.is_file():
                found_files.append(file)
    return found_files


def find_regexp_in_path(path: Path, pattern: str, *, recursive: bool = False) -> bool:
    """Search for a regexp pattern in all files under path.

    Note: file contents are read in full so patterns can span multiple lines
    (re.DOTALL is enabled).
    """
    if not (path.exists() and path.is_dir()):
        return False
    if path.name == ".git":
        return False

    for file in path.glob("*"):
        if file.is_dir():
            if recursive and find_regexp_in_path(file, pattern, recursive=True):
                return True
            continue
        try:
            content = file.read_text()
        except UnicodeDecodeError:
            print(f"WARNING: couldn't decode {file}, skipping.")
            continue
        if re.search(pattern, content, re.DOTALL):
            return True
    return False
