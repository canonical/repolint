# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

from datetime import datetime

from repolint.checks import CheckResult, list_checks
from repolint.utils import get_repository_details_filename, sanitize


def render_markdown_details(repo: str, results: dict[str, CheckResult]) -> str:
    """Render a detailed per-repository compliance report as a nested Markdown list.

    Structure: one top-level bullet per ParentCheck, with its leaf checks
    indented beneath it.  Internal helper checks (parent='_internal') are
    omitted as they are implementation details, not user-facing criteria.
    """
    markdown = f"# {repo}\n\n"
    for parent in [c for c in list_checks() if not c.parent]:
        parent_result = results.get(parent.name)
        if parent_result is None:
            continue
        parent_desc = sanitize(parent.description)
        line = f"- <span title='{parent_desc}'>{parent.name}</span>: {parent_result.result}"
        if parent_result.message:
            line += f" — {parent_result.message}"
        markdown += line + "\n"

        for child in [c for c in list_checks() if c.parent == parent.name]:
            child_result = results.get(child.name)
            if child_result is None:
                continue
            child_desc = sanitize(child.description)
            child_line = (
                f"  - <span title='{child_desc}'>{child.name}</span>: {child_result.result}"
            )
            if child_result.message:
                child_line += f" — {child_result.message}"
            markdown += child_line + "\n"

        markdown += "\n"
    return markdown


def render_markdown_overview(results: dict[str, dict[str, CheckResult]]) -> str:
    """Render a Markdown table summarising all repositories against visible criteria."""
    visible_checks = [c for c in list_checks() if not c.parent]
    headers = ["Repository"] + [
        f"<span title='{sanitize(c.description)}'>{c.name}</span>" for c in visible_checks
    ]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for repo, repo_results in results.items():
        details_file = get_repository_details_filename(repo)
        row = [f"[{repo}](https://github.com/{repo}) [🔍]({details_file})"]
        for check in visible_checks:
            result = repo_results.get(check.name)
            if result is None:
                raise RuntimeError(f"Missing result for {check.name} in repository {repo}.")
            msg = sanitize(result.message)
            row.append(f"<span title='{msg}'>{result.result}</span>")
        table.append("| " + " | ".join(row) + " |")

    return "\n".join(table) + "\n\nLast updated: " + datetime.now().isoformat()


def analyze_repo(repo: str) -> dict[str, CheckResult]:
    """Run all compliance checks for a single repository and return the results."""
    repo_results: dict[str, CheckResult] = {}
    for check in list_checks():
        repo_results[check.name] = check(repo, previous_results=repo_results)
    return repo_results


def analyze(repositories: list[str]) -> dict[str, dict[str, CheckResult]]:
    """Run compliance checks for a list of repositories."""
    print("Analyzing the following repositories:")
    print("\n".join(sorted(repositories)))
    return {repo: analyze_repo(repo) for repo in sorted(repositories)}
