# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Report rendering and repository analysis orchestration."""

from datetime import datetime

from repolint.checks import CheckResult, aggregate_check, get_check_function
from repolint.criteria import get_criterion_by_name, list_criteria
from repolint.utils import get_repository_details_filename, sanitize


def render_markdown_details(repo: str, results: dict[str, CheckResult]) -> str:
    """Render a detailed per-repository compliance report as Markdown."""
    markdown = f"# {repo}\n\n"
    for criterion_name, value in results.items():
        criterion_info = get_criterion_by_name(criterion_name)
        if criterion_info is None:
            continue
        aggregate_label = "(aggregate) " if criterion_info.get("aggregates") else ""
        description = sanitize(criterion_info["description"])
        markdown += (
            f"- {aggregate_label}"
            f"<span title='{description}'>{criterion_name}</span>: {value['result']}\n"
        )
        if value.get("message"):
            markdown += f"  - {value['message']}\n"
        markdown += "\n"
    return markdown


def render_markdown_overview(results: dict[str, dict[str, CheckResult]]) -> str:
    """Render a Markdown table summarising all repositories against visible criteria."""
    visible_criteria = [c for c in list_criteria() if not c.get("hidden")]
    headers = ["Repository"] + [
        "<span title='{desc}'>{name}</span>".format(
            desc=sanitize(c["description"]), name=c["name"]
        )
        for c in visible_criteria
    ]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for repo, repo_results in results.items():
        details_file = get_repository_details_filename(repo)
        row = [f"[{repo}](https://github.com/{repo}) [🔍]({details_file})"]
        for criterion in visible_criteria:
            result = repo_results.get(criterion["name"])
            if result is None:
                raise RuntimeError(f"Missing result for {criterion['name']} in repository {repo}.")
            msg = sanitize(result.get("message", ""))
            row.append(f"<span title='{msg}'>{result.get('result', '')}</span>")
        table.append("| " + " | ".join(row) + " |")

    return "\n".join(table) + "\n\nLast updated: " + datetime.now().isoformat()


def analyze_repo(repo: str) -> dict[str, CheckResult]:
    """Run all compliance checks for a single repository and return the results."""
    repo_results: dict[str, CheckResult] = {}
    for criterion in list_criteria():
        if criterion.get("aggregates"):
            check_fn = aggregate_check
        else:
            check_fn = get_check_function(criterion["name"])  # type: ignore[assignment]
        if check_fn is None:
            raise RuntimeError(f"Check function for criterion {criterion['name']!r} not found.")
        repo_results[criterion["name"]] = check_fn(
            repo, previous_results=repo_results, check_name=criterion["name"]
        )
    return repo_results


def analyze(repositories: list[str]) -> dict[str, dict[str, CheckResult]]:
    """Run compliance checks for a list of repositories."""
    print("Analyzing the following repositories:")
    print("\n".join(sorted(repositories)))
    return {repo: analyze_repo(repo) for repo in sorted(repositories)}
