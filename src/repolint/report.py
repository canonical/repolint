# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

import re
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown

from repolint.checks import CheckResult, list_checks
from repolint.config import CheckStatus
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


def render_markdown_overview(quality_data: dict, output: str | None = None) -> str:
    """Render a Markdown table summarising all repositories against visible criteria.

    *quality_data* is the full quality JSON structure (``{"metadata": …,
    "results": …}``).  Only registered parent checks (those that have a result
    entry for each repository) appear as table columns.

    When *output* is provided, each parent check column header is linked to the
    corresponding parent check page ``{output}-{check_name}.md``.
    """
    checks_meta: list[dict] = quality_data["metadata"]["checks"]
    results: dict = quality_data["results"]

    # Visible checks are registered parent checks — they always have a description
    # string.  Unregistered helper groups (e.g. _internal) carry description=None.
    visible_checks = [c for c in checks_meta if c["description"] is not None]

    def _check_header(c: dict) -> str:
        desc = sanitize(c["description"] or "")
        if output is not None:
            return f"<span title='{desc}'>[{c['name']}]({output}-{c['name']}.md)</span>"
        return f"<span title='{desc}'>{c['name']}</span>"

    headers = ["Repository"] + [_check_header(c) for c in visible_checks]
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


def render_markdown_parent_check(
    parent_name: str,
    parent_description: str,
    children_meta: list[dict],
    quality_data: dict,
    output: str,
) -> str:
    """Render a per-parent-check Markdown report across all repositories.

    The report is a table with repos as rows and each subcheck as a column.
    Each subcheck column header links to the corresponding
    ``{output}-{subcheck_name}.md`` detail page.
    """
    results: dict = quality_data["results"]

    def _subcheck_header(child: dict) -> str:
        desc = sanitize(child.get("description") or "")
        return f"<span title='{desc}'>[{child['name']}]({output}-{child['name']}.md)</span>"

    headers = ["Repository"] + [_subcheck_header(c) for c in children_meta]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for repo, repo_results in results.items():
        details_file = get_repository_details_filename(repo)
        row = [f"[{repo}](https://github.com/{repo}) [🔍]({details_file})"]
        for child in children_meta:
            result = repo_results.get(child["name"])
            if result is None:
                row.append("")
            else:
                msg = sanitize(result["message"])
                row.append(f"<span title='{msg}'>{result['result']}</span>")
        table.append("| " + " | ".join(row) + " |")

    desc_suffix = f" — {parent_description}" if parent_description else ""
    markdown = f"# {parent_name}{desc_suffix}\n\n"
    markdown += "\n".join(table) + "\n"
    return markdown


def render_markdown_subcheck(
    subcheck_name: str, subcheck_description: str, quality_data: dict
) -> str:
    """Render a per-subcheck Markdown report across all repositories.

    The report has three sections — **Failed**, **Passed**, and **Excluded** —
    each containing a table with a repository column and a single result column
    for *subcheck_name*.
    """
    results: dict = quality_data["results"]

    failed: list[tuple[str, dict]] = []
    passed: list[tuple[str, dict]] = []
    excluded: list[tuple[str, dict]] = []

    for repo, repo_results in results.items():
        result = repo_results.get(subcheck_name)
        if result is None:
            continue
        status = result["result"]
        if status == CheckStatus.NOT_COMPLIANT:
            failed.append((repo, result))
        elif status == CheckStatus.COMPLIANT:
            passed.append((repo, result))
        else:
            excluded.append((repo, result))

    def _make_table(rows: list[tuple[str, dict]]) -> str:
        if not rows:
            return "_None._\n"
        header = f"| Repository | {subcheck_name} |"
        separator = "| --- | --- |"
        table_rows = []
        for repo, result in rows:
            details_file = get_repository_details_filename(repo)
            repo_cell = f"[{repo}](https://github.com/{repo}) [🔍]({details_file})"
            msg = sanitize(result["message"])
            result_cell = f"<span title='{msg}'>{result['result']}</span>"
            table_rows.append(f"| {repo_cell} | {result_cell} |")
        return "\n".join([header, separator, *table_rows]) + "\n"

    desc_suffix = f" — {subcheck_description}" if subcheck_description else ""
    markdown = f"# {subcheck_name}{desc_suffix}\n\n"
    markdown += "## Failed\n\n"
    markdown += _make_table(failed)
    markdown += "\n## Passed\n\n"
    markdown += _make_table(passed)
    markdown += "\n## Excluded\n\n"
    markdown += _make_table(excluded)

    return markdown


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
