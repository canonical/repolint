# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base class, registry and cross-cutting helpers for repository compliance checks."""

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from repolint.config import CheckStatus

# Per-check configuration loaded from repolint.yaml.  Populated by
# configure_checks() which is called from the CLI entry point before any
# analysis runs.
_checks_overrides: dict[str, dict] = {}


def configure_checks(checks_config: dict[str, dict]) -> None:
    """Set per-check configuration sourced from the repolint.yaml ``checks`` key.

    *checks_config* is expected to be a mapping of check name → check options.
    Currently only ``excluded`` (a list of ``org/repo`` strings) is supported::

        {
            "squad_topic": {"excluded": ["canonical/cbartz-runner-testing"]},
            "github2jira": {"excluded": ["canonical/gatekeeper-repo-test"]},
        }

    Calling this function again replaces any previously configured overrides.
    """
    global _checks_overrides
    _checks_overrides = checks_config


@dataclass
class CheckResult:
    """Result of a single compliance check."""

    result: CheckStatus
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain dict for JSON output."""
        return {"result": self.result.value, "message": self.message}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "CheckResult":
        """Deserialise from a plain dict (e.g. loaded from JSON cache)."""
        return cls(result=CheckStatus(data["result"]), message=data.get("message", ""))


# Registry mapping criterion name → Check instance
_REGISTRY: dict[str, "Check"] = {}


class Check(ABC):
    """Abstract base class for all repository compliance checks.

    Subclasses must define ``name`` and ``description`` as class attributes
    and implement ``run()``.  Defining ``name`` on a subclass automatically
    registers an instance in the global ``_REGISTRY`` via ``__init_subclass__``.
    """

    name: str  # class attribute — subclasses must define this
    description: str  # human-readable description — subclasses must define this
    depends_on: ClassVar[list[str]] = []  # names of checks that must pass first
    hidden: bool = False  # if True, not shown in overview report
    aggregates: ClassVar[list[str]] = []  # sub-check names (only for AggregateCheck)

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

        # Config-based exclusion
        config_excluded: list[str] = _checks_overrides.get(self.name, {}).get("excluded", [])
        if repo in config_excluded:
            return CheckResult(CheckStatus.NOT_ELIGIBLE, "Repository is excluded from this check.")

        # Dependency check
        for dependency in self.depends_on:
            if dependency not in previous_results:
                raise RuntimeError(
                    f"[{repo}][{self.name}] Couldn't find the result of the {dependency!r} dependency."
                )
            dep_result = previous_results[dependency].result
            if dep_result != CheckStatus.COMPLIANT:
                return CheckResult(
                    CheckStatus.NOT_ELIGIBLE,
                    f"Skipped. Depends on {dependency} which is {dep_result}.",
                )

        # Aggregate check
        if self.aggregates:
            missing = [n for n in self.aggregates if n not in previous_results]
            if missing:
                raise RuntimeError(f"Couldn't find the result of {missing} for {repo}.")
            failed = [
                n
                for n in self.aggregates
                if previous_results[n].result == CheckStatus.NOT_COMPLIANT
            ]
            if failed:
                return CheckResult(
                    CheckStatus.NOT_COMPLIANT,
                    f"Subcheck(s) {', '.join(failed)} is/are not compliant.",
                )
            return CheckResult(
                CheckStatus.COMPLIANT,
                f"All subchecks {', '.join(self.aggregates)} are compliant.",
            )

        try:
            return self.run(repo, previous_results)
        except subprocess.CalledProcessError as e:
            return CheckResult(CheckStatus.NOT_COMPLIANT, f"Failed to clone repository: {e}")


class AggregateCheck(Check):
    """Check whose result is derived entirely from sub-checks; ``run()`` is never called."""

    def __init__(
        self,
        aggregate_name: str,
        description: str = "",
        depends_on: list[str] | None = None,
        aggregates: list[str] | None = None,
        hidden: bool = False,
    ) -> None:
        self._name = aggregate_name
        self._description = description
        self._depends_on = depends_on or []
        self._aggregates = aggregates or []
        self._hidden = hidden
        _REGISTRY[aggregate_name] = self

    @property  # type: ignore[override]
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @property  # type: ignore[override]
    def description(self) -> str:  # type: ignore[override]
        return self._description

    @property  # type: ignore[override]
    def depends_on(self) -> list[str]:  # type: ignore[override]
        return self._depends_on

    @property  # type: ignore[override]
    def aggregates(self) -> list[str]:  # type: ignore[override]
        return self._aggregates

    @property  # type: ignore[override]
    def hidden(self) -> bool:  # type: ignore[override]
        return self._hidden

    def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
        raise RuntimeError(
            "AggregateCheck.run() should never be called directly."
        )  # pragma: no cover


def get_check(name: str) -> "Check | None":
    """Return the registered Check instance for a given name, or None."""
    return _REGISTRY.get(name)


def list_checks() -> list[Check]:
    """Return all registered checks in dependency-sorted order."""
    visited: set[str] = set()
    result: list[Check] = []

    def _visit(name: str) -> None:
        if name in visited:
            return
        check = _REGISTRY.get(name)
        if check is None:
            return
        for dep in check.depends_on:
            _visit(dep)
        visited.add(name)
        result.append(check)

    for name in _REGISTRY:
        _visit(name)
    return result
