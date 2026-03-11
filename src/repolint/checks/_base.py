# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base class, registry and cross-cutting helpers for repository compliance checks."""

from abc import ABC, abstractmethod

from repolint.config import CHECK_COMPLIANT, CHECK_NOT_COMPLIANT, CHECK_NOT_ELIGIBLE
from repolint.criteria import get_criterion_by_name

# Type alias for a check result dict: {"result": ..., "message": ...}
CheckResult = dict[str, str]

# Registry mapping criterion name → Check instance
_REGISTRY: dict[str, "Check"] = {}


def _check_exclusion(repo: str, criterion: dict) -> CheckResult | None:
    """Return NOT_ELIGIBLE if *repo* is in the criterion's exclusion list, else None."""
    if repo in criterion.get("excluded", []):
        return {"result": CHECK_NOT_ELIGIBLE, "message": "Repository is excluded from this check."}
    return None


def _check_dependencies(
    repo: str,
    name: str,
    criterion: dict,
    previous_results: dict[str, CheckResult],
) -> CheckResult | None:
    """Return NOT_ELIGIBLE if any dependency is not compliant, raise if missing, else None."""
    for dependency in criterion.get("depends_on", []):
        if dependency not in previous_results:
            raise RuntimeError(
                f"[{repo}][{name}] Couldn't find the result of the {dependency!r} dependency."
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


class Check(ABC):
    """Abstract base class for all repository compliance checks.

    Subclasses must define ``name`` and ``description`` as class attributes
    and implement ``run()``.  Defining ``name`` on a subclass automatically
    registers an instance in the global ``_REGISTRY`` via ``__init_subclass__``.
    """

    name: str  # class attribute — subclasses must define this
    description: str  # human-readable description — subclasses must define this

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-register only concrete subclasses that declare name as a plain class attribute
        # (not a property, which AggregateCheck uses for its dynamic name).
        name_attr = cls.__dict__.get("name")
        if isinstance(name_attr, str):
            _REGISTRY[cls.name] = cls()

    @abstractmethod
    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        """Execute the check logic for *repo* and return a CheckResult."""

    def __call__(
        self,
        repo: str,
        previous_results: dict[str, CheckResult] | None = None,
    ) -> CheckResult:
        """Run the check with cross-cutting behaviour (exclusion, deps, aggregates)."""
        if previous_results is None:
            previous_results = {}

        criterion = get_criterion_by_name(self.name)
        if criterion is None:
            raise RuntimeError(f"Unknown criterion: {self.name!r}")

        if (early := _check_exclusion(repo, criterion)) is not None:
            return early
        if (
            early := _check_dependencies(repo, self.name, criterion, previous_results)
        ) is not None:
            return early
        if (early := _check_aggregates(repo, criterion, previous_results)) is not None:
            return early

        result = self.run(repo, previous_results)
        return result


class AggregateCheck(Check):
    """Check whose result is derived entirely from sub-checks; ``run()`` is never called."""

    def __init__(self, aggregate_name: str, description: str = "") -> None:
        self._name = aggregate_name
        self._description = description

    @property  # type: ignore[override]
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @property  # type: ignore[override]
    def description(self) -> str:  # type: ignore[override]
        return self._description

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        raise RuntimeError(
            "AggregateCheck.run() should never be called directly."
        )  # pragma: no cover


def get_check_function(name: str) -> Check | None:
    """Return the registered Check instance for a criterion name, or None."""
    return _REGISTRY.get(name)
