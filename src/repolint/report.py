# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

import re
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown

from repolint.checks import CheckResult, list_checks
from repolint.utils import get_repository_details_filename, sanitize

_SPAN_TAG_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.DOTALL)


def render_report_in_terminal(content: str) -> None:
    """Render a Markdown report string in the terminal using rich.

    HTML <span> tags (used for browser tooltip hints) are stripped so the
    terminal output contains only the readable text they wrap.
    """
    plain = _SPAN_TAG_RE.sub(r"\1", content)
    Console().print(Markdown(plain))


def _render_child_checks(children: list[dict], results: dict) -> str:
    """Return Markdown lines for child checks given a list of child metadata dicts."""
    lines = ""
    for child in children:
        child_result = results.get(child["name"])
        if child_result is None:
            continue
        child_desc = sanitize(child["description"] or "")
        line = f"  - <span title='{child_desc}'>{child['name']}</span>: {child_result['result']}"
        if child_result["message"]:
            line += f" — {child_result['message']}"
        lines += line + "\n"
    return lines


def render_markdown_details(repo: str, quality_data: dict) -> str:
    """Render a detailed per-repository compliance report as a nested Markdown list.

    *quality_data* is the full quality JSON structure (``{"metadata": …,
    "results": …}``).  Structure: one top-level bullet per registered parent
    check, with its leaf checks indented beneath it.  Unregistered helper
    groups (e.g. ``_internal``) appear at the end without their own result.
    """
    checks_meta: list[dict] = quality_data["metadata"]["checks"]
    repo_results: dict = quality_data["results"][repo]

    markdown = f"# {repo}\n\n"

    for check_group in checks_meta:
        group_name = check_group["name"]
        group_result = repo_results.get(group_name)

        if group_result is not None:
            # Registered parent — renders its own result line.
            group_desc = sanitize(check_group["description"] or "")
            line = f"- <span title='{group_desc}'>{group_name}</span>: {group_result['result']}"
            if group_result["message"]:
                line += f" — {group_result['message']}"
            markdown += line + "\n"
        else:
            # Unregistered helper group (e.g. _internal) — no result of its own.
            markdown += f"- {group_name}\n"

        markdown += _render_child_checks(check_group["children"], repo_results)
        markdown += "\n"

    return markdown


def render_markdown_overview(quality_data: dict) -> str:
    """Render a Markdown table summarising all repositories against visible criteria.

    *quality_data* is the full quality JSON structure (``{"metadata": …,
    "results": …}``).  Only registered parent checks (those that have a result
    entry for each repository) appear as table columns.
    """
    checks_meta: list[dict] = quality_data["metadata"]["checks"]
    results: dict = quality_data["results"]

    # Visible checks are registered parent checks — they always have a description
    # string.  Unregistered helper groups (e.g. _internal) carry description=None.
    visible_checks = [c for c in checks_meta if c["description"] is not None]

    headers = ["Repository"] + [
        f"<span title='{sanitize(c['description'] or '')}'>{c['name']}</span>"
        for c in visible_checks
    ]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for repo, repo_results in results.items():
        details_file = get_repository_details_filename(repo)
        row = [f"[{repo}](https://github.com/{repo}) [🔍]({details_file})"]
        for check in visible_checks:
            result = repo_results.get(check["name"])
            if result is None:
                raise RuntimeError(f"Missing result for {check['name']} in repository {repo}.")
            msg = sanitize(result["message"])
            row.append(f"<span title='{msg}'>{result['result']}</span>")
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

