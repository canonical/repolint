# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

import re
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown

from repolint.checks import Check, CheckResult, list_checks
from repolint.utils import get_repository_details_filename, sanitize

_SPAN_TAG_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.DOTALL)


def render_report_in_terminal(content: str) -> None:
    """Render a Markdown report string in the terminal using rich.

    HTML <span> tags (used for browser tooltip hints) are stripped so the
    terminal output contains only the readable text they wrap.
    """
    plain = _SPAN_TAG_RE.sub(r"\1", content)
    Console().print(Markdown(plain))


def _render_child_checks(
    group_name: str, all_checks: list[Check], results: dict[str, CheckResult]
) -> str:
    """Return Markdown lines for checks whose parent equals *group_name*."""
    lines = ""
    for child in [c for c in all_checks if c.parent == group_name]:
        child_result = results.get(child.name)
        if child_result is None:
            continue
        child_desc = sanitize(child.description)
        line = f"  - <span title='{child_desc}'>{child.name}</span>: {child_result.result}"
        if child_result.message:
            line += f" — {child_result.message}"
        lines += line + "\n"
    return lines


def render_markdown_details(repo: str, results: dict[str, CheckResult]) -> str:
    """Render a detailed per-repository compliance report as a nested Markdown list.

    Structure: one top-level bullet per ParentCheck, with its leaf checks
    indented beneath it.  Checks whose parent is not a registered check (e.g.
    the ``_internal`` helper group) are rendered as additional sections at the
    end of the report.
    """
    all_checks = list_checks()
    registered_names = {c.name for c in all_checks}

    markdown = f"# {repo}\n\n"

    for parent in [c for c in all_checks if not c.parent]:
        parent_result = results.get(parent.name)
        if parent_result is None:
            continue
        parent_desc = sanitize(parent.description)
        line = f"- <span title='{parent_desc}'>{parent.name}</span>: {parent_result.result}"
        if parent_result.message:
            line += f" — {parent_result.message}"
        markdown += line + "\n"
        markdown += _render_child_checks(parent.name, all_checks, results)
        markdown += "\n"

    # Render unregistered parent groups (e.g. "_internal").
    unregistered_parents = sorted(
        {c.parent for c in all_checks if c.parent and c.parent not in registered_names}
    )
    for group_name in unregistered_parents:
        markdown += f"- {group_name}\n"
        markdown += _render_child_checks(group_name, all_checks, results)
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
