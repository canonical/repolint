# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Check functions for repository compliance, with a registration decorator."""

import functools
import subprocess
from collections.abc import Callable
from typing import Any

from repolint.config import (
    CHECK_COMPLIANT,
    CHECK_NOT_COMPLIANT,
    CHECK_NOT_ELIGIBLE,
    SQUAD_TOPICS,
)
from repolint.criteria import get_criterion_by_name
from repolint.utils import (
    clone_repository_locally,
    find_charmcraft_paths,
    find_files_in_path,
    find_regexp_in_path,
    get_repository_topics,
)

# Type alias for a check result dict: {"result": ..., "message": ...}
CheckResult = dict[str, str]

# Registry mapping criterion name → decorated check callable
_REGISTRY: dict[str, Callable[..., CheckResult]] = {}


def _check_exclusion(repo: str, criterion: dict) -> CheckResult | None:
    """Return NOT_ELIGIBLE if *repo* is in the criterion's exclusion list, else None."""
    if repo in criterion.get("excluded", []):
        return {"result": CHECK_NOT_ELIGIBLE, "message": "Repository is excluded from this check."}
    return None


def _check_dependencies(
    repo: str,
    resolved_name: str,
    criterion: dict,
    previous_results: dict[str, CheckResult],
) -> CheckResult | None:
    """Return NOT_ELIGIBLE if any dependency is not compliant, raise if missing, else None."""
    for dependency in criterion.get("depends_on", []):
        if dependency not in previous_results:
            raise RuntimeError(
                f"[{repo}][{resolved_name}] Couldn't find the result of the {dependency!r} dependency."
            )
        dep_result = previous_results[dependency]["result"]
        if dep_result != CHECK_COMPLIANT:
            return {
                "result": CHECK_NOT_ELIGIBLE,
                "message": f"Skipped. Depends on {dependency} which is {dep_result}.",
            }
    return None


def _check_aggregates(
    repo: str, criterion: dict, previous_results: dict[str, CheckResult]
) -> CheckResult | None:
    """Return aggregate result if criterion has aggregates, else None."""
    aggregates: list[str] = criterion.get("aggregates", [])
    if not aggregates:
        return None
    missing = [name for name in aggregates if name not in previous_results]
    if missing:
        raise RuntimeError(f"Couldn't find the result of {missing} for {repo}.")
    failed = [
        name for name in aggregates if previous_results[name]["result"] == CHECK_NOT_COMPLIANT
    ]
    if failed:
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": f"Subcheck(s) {', '.join(failed)} is/are not compliant.",
        }
    return {
        "result": CHECK_COMPLIANT,
        "message": f"All subchecks {', '.join(aggregates)} are compliant.",
    }


def check(func: Callable[..., CheckResult | None]) -> Callable[..., CheckResult]:
    """Decorate a check function with common cross-cutting behaviour.

    - Skips excluded repositories (returns NOT_ELIGIBLE).
    - Skips checks whose dependencies are not compliant (returns NOT_ELIGIBLE).
    - Handles aggregate checks automatically, without calling the function body.

    The decorated function is registered in the module-level ``_REGISTRY``
    under the criterion name derived from its ``__name__``.
    """

    @functools.wraps(func)
    def wrapper(
        repo: str,
        previous_results: dict[str, CheckResult] | None = None,
        check_name: str | None = None,
    ) -> CheckResult:
        if previous_results is None:
            previous_results = {}

        resolved_name = check_name or func.__name__.replace("check_repository_", "")
        criterion = get_criterion_by_name(resolved_name)
        if criterion is None:
            raise RuntimeError(f"Unknown criterion: {resolved_name!r}")

        if (early := _check_exclusion(repo, criterion)) is not None:
            return early
        if (
            early := _check_dependencies(repo, resolved_name, criterion, previous_results)
        ) is not None:
            return early
        if (early := _check_aggregates(repo, criterion, previous_results)) is not None:
            return early

        result = func(repo, previous_results=previous_results)
        if result is None:  # pragma: no cover
            raise RuntimeError(f"Check {resolved_name!r} returned None unexpectedly.")
        return result

    name = func.__name__.replace("check_repository_", "")
    _REGISTRY[name] = wrapper
    return wrapper


def get_check_function(name: str) -> Callable[..., CheckResult] | None:
    """Return the registered check callable for a criterion name, or None."""
    return _REGISTRY.get(name)


# ---------------------------------------------------------------------------
# Aggregate placeholder — the decorator handles all aggregate logic; the body
# is never reached for aggregate criteria.
# ---------------------------------------------------------------------------


@check
def aggregate_check(repo: str, previous_results: dict[str, Any] | None = None) -> CheckResult:
    """Placeholder for aggregate checks; all logic is in the @check decorator."""
    raise RuntimeError("aggregate_check body should never be reached.")  # pragma: no cover


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


@check
def check_repository_pfe_topic(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository has the 'platform-engineering' topic."""
    topics = get_repository_topics(repo)
    if "platform-engineering" in topics:
        return {"result": CHECK_COMPLIANT, "message": ""}
    return {"result": CHECK_NOT_COMPLIANT, "message": "No platform-engineering topic found."}


@check
def check_repository_squad_topic(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository has a squad-xxx topic."""
    topics = get_repository_topics(repo)
    if any(topic in SQUAD_TOPICS for topic in topics):
        return {"result": CHECK_COMPLIANT, "message": ""}
    return {"result": CHECK_NOT_COMPLIANT, "message": "No squad topic found."}


@check
def check_repository_product_topic(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository has a product-xxx topic."""
    topics = get_repository_topics(repo)
    if any(topic.startswith("product-") for topic in topics):
        return {"result": CHECK_COMPLIANT, "message": ""}
    return {"result": CHECK_NOT_COMPLIANT, "message": "No product topic found."}


@check
def check_repository_github2jira(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository has a GitHub-to-Jira sync configuration."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    integration_conf_file = local_repo / ".github/.jira_sync_config.yaml"
    if integration_conf_file.exists():
        return {"result": CHECK_COMPLIANT, "message": ""}
    return {
        "result": CHECK_NOT_COMPLIANT,
        "message": "No GitHub to Jira integration config found.",
    }


@check
def check_repository_contains_charm(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository contains at least one charm."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    charms = find_charmcraft_paths(local_repo)
    if charms:
        return {
            "result": CHECK_COMPLIANT,
            "message": "Charms in: " + ", ".join(str(k) for k in charms),
        }
    return {"result": CHECK_NOT_COMPLIANT, "message": "No charms found in the repository."}


@check
def check_repository_contains_k8s_charm(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository contains at least one Kubernetes charm."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    charms = find_charmcraft_paths(local_repo)
    k8s_charms = [charm for charm in charms if "k8s-api" in charm.read_text()]
    if k8s_charms:
        return {
            "result": CHECK_COMPLIANT,
            "message": "Kubernetes charms in: " + ", ".join(str(k) for k in k8s_charms),
        }
    return {"result": CHECK_NOT_COMPLIANT, "message": "No k8s charms found in the repository."}


@check
def check_repository_ck8s(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository's GitHub workflows use canonical Kubernetes."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    expected_conf = "use-canonical-k8s: true"
    if find_regexp_in_path(local_repo / ".github/workflows", expected_conf):
        return {"result": CHECK_COMPLIANT, "message": ""}
    return {
        "result": CHECK_NOT_COMPLIANT,
        "message": f"No '{expected_conf}' found in GitHub workflow files.",
    }


@check
def check_repository_juju4(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository has at least one workflow targeting Juju 4."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    expected_conf = "juju-channel:.*4/stable"
    if find_regexp_in_path(local_repo / ".github/workflows", expected_conf):
        return {"result": CHECK_COMPLIANT, "message": "At least one workflow uses Juju 4."}
    return {
        "result": CHECK_NOT_COMPLIANT,
        "message": f"No '{expected_conf}' found in GitHub workflow files.",
    }


@check
def check_repository_jubilant(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that all charms use Jubilant for integration testing."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    expected_conf = "import jubilant"
    found = [
        find_regexp_in_path(charm.parent / "tests" / "integration", pattern=expected_conf)
        for charm in find_charmcraft_paths(local_repo)
    ]
    if all(found):
        return {"result": CHECK_COMPLIANT, "message": "All tests use Jubilant."}
    if any(found):
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": "Some integration tests use Jubilant, but not all charms have it.",
        }
    return {
        "result": CHECK_NOT_COMPLIANT,
        "message": f"No '{expected_conf}' found in integration tests.",
    }


@check
def check_repository_tf_v1(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that all Terraform modules use Juju provider v1."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    expected_conf = r'juju\s*=\s*\{.*?\bversion\s*=\s*"~> 1\.'
    results = [
        find_regexp_in_path(tf_file.parent, expected_conf)
        for tf_file in find_files_in_path(local_repo, "versions.tf")
    ]
    if all(results):
        return {
            "result": CHECK_COMPLIANT,
            "message": "All Terraform provider versions files use Juju provider v1.",
        }
    if any(results):
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": "Some Terraform provider versions files use Juju provider v1, but not all.",
        }
    return {
        "result": CHECK_NOT_COMPLIANT,
        "message": f"No '{expected_conf}' found in the repository.",
    }


@check
def check_repository_charmlibs(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository does not use deprecated operator_libs_linux.

    Reference:
    - https://documentation.ubuntu.com/charmlibs/reference/general-libs/
    - https://documentation.ubuntu.com/charmlibs/reference/interface-libs/
    """
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    pattern = "from charms.operator_libs_linux"
    if find_regexp_in_path(local_repo, pattern=pattern, recursive=True):
        return {
            "result": CHECK_NOT_COMPLIANT,
            "message": "Found imports of charms.operator_libs_linux.",
        }
    return {
        "result": CHECK_COMPLIANT,
        "message": "No reference to charms.operator_libs_linux found.",
    }


@check
def check_repository_ops_testing(
    repo: str, previous_results: dict[str, Any] | None = None
) -> CheckResult:
    """Check that the repository uses ops.testing instead of the old Harness."""
    try:
        local_repo = clone_repository_locally(repo)
    except subprocess.CalledProcessError as e:
        return {"result": CHECK_NOT_COMPLIANT, "message": f"Failed to clone repository: {e}"}
    if find_regexp_in_path(local_repo, pattern="harness", recursive=True):
        return {"result": CHECK_NOT_COMPLIANT, "message": "Found references to harness."}
    return {"result": CHECK_COMPLIANT, "message": "No reference to harness found."}
