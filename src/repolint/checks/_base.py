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
    Supported options:

    - ``excluded``: a list of ``org/repo`` strings to skip for that check.
    - ``patterns``: (``github_topics`` only) a list of regexp strings; at
      least one repository topic must match each pattern.

    Example::

        {
            "github_topics": {"patterns": ["^squad-", "^product-"]},
            "github2jira": {"excluded": ["canonical/gatekeeper-repo-test"]},
        }

    Calling this function again replaces any previously configured overrides.
    """
    global _checks_overrides
    _checks_overrides = checks_config


def get_check_config(name: str) -> dict:
    """Return the configuration dict for the named check, or an empty dict."""
    return _checks_overrides.get(name, {})


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

    Subclasses must define ``name``, ``description``, and ``parent`` as class
    attributes and implement ``run()``.  Defining ``name`` on a subclass
    automatically registers an instance in the global ``_REGISTRY`` via
    ``__init_subclass__``.
    """

    name: str  # class attribute — subclasses must define this
    description: str  # human-readable description — subclasses must define this
    parent: str  # name of the ParentCheck this check belongs to, or "" if none
    depends_on: ClassVar[list[str]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-register only concrete subclasses that declare name as a plain
        # class attribute (not a property, which ParentCheck uses).
        name_attr = cls.__dict__.get("name")
        if isinstance(name_attr, str):
            for attr in ("description", "parent"):
                if not isinstance(cls.__dict__.get(attr), str):
                    raise TypeError(
                        f"{cls.__name__} must define '{attr}' as a class-level string attribute."
                    )
            _REGISTRY[cls.name] = cls()

    @abstractmethod
    def run(self, repo: str) -> CheckResult:
        """Execute the check logic for *repo* and return a CheckResult."""

    def _apply_pre_checks(
        self, repo: str, previous_results: dict[str, CheckResult]
    ) -> "CheckResult | None":
        """Return a short-circuit CheckResult for exclusion/dependency, or None."""
        config_excluded: list[str] = _checks_overrides.get(self.name, {}).get("excluded", [])
        if repo in config_excluded:
            return CheckResult(CheckStatus.NOT_ELIGIBLE, "Repository is excluded from this check.")
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
        return None

    def __call__(
        self,
        repo: str,
        previous_results: dict[str, CheckResult] | None = None,
    ) -> CheckResult:
        """Run the check with cross-cutting behaviour (exclusion, deps)."""
        if previous_results is None:
            previous_results = {}
        pre = self._apply_pre_checks(repo, previous_results)
        if pre is not None:
            return pre
        try:
            return self.run(repo)
        except subprocess.CalledProcessError as e:
            return CheckResult(CheckStatus.NOT_COMPLIANT, f"Failed to clone repository: {e}")


class ParentCheck(Check):
    """Check whose result is derived from child checks; ``run()`` is never called."""

    parent = ""

    def __init__(
        self,
        name: str,
        description: str = "",
        depends_on: list[str] | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._depends_on = depends_on or []
        _REGISTRY[name] = self

    @property  # type: ignore[override]
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @property  # type: ignore[override]
    def description(self) -> str:  # type: ignore[override]
        return self._description

    @property  # type: ignore[override]
    def depends_on(self) -> list[str]:  # type: ignore[override]
        return self._depends_on

    def run(self, repo: str) -> CheckResult:
        raise RuntimeError(
            "ParentCheck.run() should never be called directly."
        )  # pragma: no cover

    def __call__(
        self,
        repo: str,
        previous_results: dict[str, CheckResult] | None = None,
    ) -> CheckResult:
        """Derive result from child checks."""
        if previous_results is None:
            previous_results = {}
        pre = self._apply_pre_checks(repo, previous_results)
        if pre is not None:
            return pre
        children = [c for c in _REGISTRY.values() if c.parent == self.name]
        missing = [c.name for c in children if c.name not in previous_results]
        if missing:
            raise RuntimeError(f"Couldn't find the result of {missing} for {repo}.")
        failed = [
            c.name
            for c in children
            if previous_results[c.name].result == CheckStatus.NOT_COMPLIANT
        ]
        if failed:
            return CheckResult(
                CheckStatus.NOT_COMPLIANT,
                f"Subcheck(s) {', '.join(failed)} is/are not compliant.",
            )
        return CheckResult(CheckStatus.COMPLIANT, "All subchecks are compliant.")


def get_check(name: str) -> "Check | None":
    """Return the registered Check instance for a given name, or None."""
    return _REGISTRY.get(name)


def list_checks() -> list[Check]:
    """Return all registered checks in dependency-sorted order (children before parents)."""
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
        if isinstance(check, ParentCheck):
            for child in _REGISTRY.values():
                if child.parent == check.name:
                    _visit(child.name)
        visited.add(name)
        result.append(check)

    for name in _REGISTRY:
        _visit(name)
    return result
