# Contributing to repolint

## Development setup

Clone the repository and install all development dependencies:

```bash
git clone https://github.com/canonical/repolint
cd repolint
uv sync --all-groups
```

## Running checks

```bash
tox -e fmt          # auto-format with ruff
tox -e lint         # codespell + ruff + mypy
tox -e unit         # pytest + coverage (no network required)
tox -e static       # bandit (medium+ severity)
tox -e integration  # CLI integration tests (requires gh auth and network)
```

> **Note:** The `tox.toml` file requires tox ≥ 4.21 with the
> [`tox-uv`](https://github.com/tox-dev/tox-uv) plugin. The
> `[tool.tox.legacy_tox_ini]` section in `pyproject.toml` provides
> compatibility with the system tox (≥ 4.0).
>
> ```bash
> # Using system tox (≥ 4.0)
> tox -e unit
>
> # Using uv-native runner (requires tox-uv)
> uvx --with tox-uv tox -e unit
> ```

## Project layout

```
src/repolint/
├── checks/
│   ├── _base.py           # Check ABC, ParentCheck, CheckResult, registry helpers
│   ├── __init__.py        # Triggers registration; defines ParentCheck instances
│   ├── squad_topic.py
│   ├── product_topic.py
│   └── ...
├── config.py              # CheckStatus enum and path/directory constants
├── report.py              # Report rendering and analysis orchestration
├── utils.py               # Shared helpers (clone, topic fetch, file search)
└── __main__.py            # CLI entry point
tests/unit/                # Unit tests (pytest)
repolint.yaml              # Your repository list and/or query (not committed)
reports/                   # Generated reports (git-ignored)
```

## Architecture overview

Every compliance check is a class that inherits from `Check` (defined in
`checks/_base.py`).  Defining the `name` class attribute on a subclass
automatically registers a singleton instance in the global `_REGISTRY` via
`__init_subclass__`.

```
Check (ABC)
├── SquadTopicCheck      name = "squad_topic"
├── ...
└── ParentCheck         name set via constructor — self-registers on __init__
```

`ParentCheck` instances are constructed in `checks/__init__.py` and derive
their result dynamically from child checks — any `Check` subclass whose
`parent` attribute matches the `ParentCheck`'s name.  Their `run()`
is never called directly.

Cross-cutting behaviour lives in `Check.__call__`:

1. **Config-based exclusion** — if the repo is listed under `checks.<name>.excluded`
   in `repolint.yaml`, the check returns `NOT_ELIGIBLE`.
2. **Dependency enforcement** — if any check listed in `depends_on` is not
   `COMPLIANT`, the check is skipped as `NOT_ELIGIBLE`.
3. **Error handling** — if `run()` raises `subprocess.CalledProcessError` (e.g.
   a repository clone failure), the check returns `NOT_COMPLIANT` with the error
   message.

`CheckResult` is a dataclass with a `CheckStatus` enum value and an optional
message string.  It serialises to/from plain dicts for JSON caching.

## Adding a new leaf check

1. Create `src/repolint/checks/<your_check_name>.py`:

   ```python
   # Copyright 2025 Canonical Ltd.
   # See LICENSE file for licensing details.

   """Check: <one-line description>."""

   from repolint.checks._base import Check, CheckResult
   from repolint.config import CheckStatus


   class MyCheck(Check):
       """<Docstring shown in generated docs>."""

       name = "my_check"
       description = "Human-readable description shown in reports."
       parent = ""   # set to a ParentCheck name to group under that parent

       def run(self, repo: str, previous_results: dict[str, CheckResult]) -> CheckResult:
           # ... implementation ...
           return CheckResult(CheckStatus.COMPLIANT, "")
   ```

   If this check requires a local clone, call `clone_repository_locally(repo)`
   from `repolint.utils` — clone errors are handled automatically by `__call__`.

2. Import the module in `checks/__init__.py` (side-effect import to trigger
   registration):

   ```python
   from repolint.checks import (  # noqa: F401
       ...
       my_check,
   )
   ```

3. If other checks depend on yours, add `depends_on = ["my_check"]` to those
   classes.  To group this check under a parent, set `parent = "my_parent"` on
   the class.

4. Add unit tests in `tests/unit/test_checks.py`.

## Adding a new parent check

Parent checks combine existing child checks — no `run()` body is needed.
Add a new `ParentCheck(...)` call in `checks/__init__.py`:

```python
ParentCheck(
    "my_parent",
    description="Passes when all child checks pass.",
    depends_on=["contains_charm"],   # pre-conditions
)
```

Then set `parent = "my_parent"` on each leaf check that should belong to it.
The parent check result is derived dynamically from all registered checks whose
`parent` attribute equals `"my_parent"`.

The parent check appears as a column in the overview Markdown table.
Set `hidden=True` to suppress it from the overview.
