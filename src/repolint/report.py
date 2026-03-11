# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

from datetime import datetime

from repolint.checks import CheckResult, get_check, list_checks
from repolint.utils import get_repository_details_filename, sanitize


def render_markdown_details(repo: str, results: dict[str, CheckResult]) -> str:
    """Render a detailed per-repository compliance report as Markdown."""
    markdown = f"# {repo}\n\n"
    for criterion_name, value in results.items():
        check = get_check(criterion_name)
        if check is None:
            continue
        description = sanitize(check.description)
        markdown += f"- <span title='{description}'>{criterion_name}</span>: {value.result}\n"
        if value.message:
            markdown += f"  - {value.message}\n"
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
