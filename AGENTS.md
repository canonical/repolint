# repolint

## Commands

```bash
# Install dependencies
uv sync --all-groups

# Format
tox -e fmt

# Lint (codespell + ruff + mypy)
tox -e lint

# Unit tests with coverage
tox -e unit

# Run a single test file or test
tox -e unit -- tests/unit/test_checks.py
tox -e unit -- tests/unit/test_checks.py::TestCheckExclusion::test_excluded_repo_returns_excluded

# Static analysis (bandit)
tox -e static

# Integration tests (requires gh CLI authenticated + network)
tox -e integration
```

> `tox.toml` requires tox ≥ 4.21 with `tox-uv`. Fallback: `tox -e unit` with system tox ≥ 4.0 via the `[tool.tox.legacy_tox_ini]` in `pyproject.toml`.

## Architecture

`repolint` is a CLI tool that evaluates GitHub repositories against compliance checks and writes Markdown/JSON reports.

### Check registry (auto-registration via `__init_subclass__`)

Every compliance check is a class inheriting from `Check` (`checks/_base.py`). Defining `name`, `description`, and `parent` as class-level string attributes on a subclass **automatically registers** a singleton instance in `_REGISTRY`. There is no manual registration step for leaf checks.

```
Check (ABC)                    ← defines __call__, _apply_pre_checks
├── <Leaf checks>              ← define name/description/parent, implement run()
└── ParentCheck                ← self-registers on __init__; run() is never called
```

`ParentCheck` instances are constructed explicitly in `checks/__init__.py`. Their result is computed dynamically from all child checks whose `parent` attribute matches the parent's name.

### Execution flow in `Check.__call__`

1. **Exclusion** — if `repo` is in `checks.<name>.excluded` in the config, return `EXCLUDED`.
2. **Dependency check** — if any check in `depends_on` is not `COMPLIANT`, return `NOT_ELIGIBLE` (or `ERROR` if the dependency itself errored).
3. **run()** — if `subprocess.CalledProcessError` is raised (e.g. `gh` CLI failure), return `ERROR`.

### Check execution order

`list_checks()` returns all checks in dependency-sorted order (children before parents). `report.py` calls checks in this order, accumulating results in `previous_results: dict[str, CheckResult]` so each check can inspect results of its dependencies.

### Key modules

| Module | Responsibility |
|---|---|
| `checks/_base.py` | `Check` ABC, `ParentCheck`, `CheckResult`, `_REGISTRY`, `list_checks()` |
| `checks/__init__.py` | Imports all leaf check modules (triggering registration); constructs `ParentCheck` instances |
| `config.py` | `CheckStatus` enum (StrEnum with emoji values), path constants, `TMP_DIR` |
| `utils.py` | `clone_repository_locally()`, `get_repository_topics()`, `find_regexp_in_path()`, config loading |
| `report.py` | Orchestrates analysis, reads/writes JSON cache, renders Markdown |
| `__main__.py` | CLI entry point (`argparse`) |

### Caching

Results are cached in `reports/quality.json`. Subsequent runs only re-run checks for repositories that are new or whose set of checks has changed. Removed repositories are pruned automatically.

### Local repo mode

When run with no arguments in a git repository, `repolint` detects the `origin` remote (`get_current_repo()`), uses the local working tree directly via `local_repo_override()` (no clone), and prints the detail report to stdout without writing files.

## Key Conventions

### Adding a new leaf check

1. Create `src/repolint/checks/<check_name>.py` with a class that:
   - Sets `name`, `description`, `parent` as **class-level strings**
   - Implements `run(self, repo: str) -> CheckResult`
   - Uses `clone_repository_locally(repo)` from `utils` if file access is needed
2. Add a side-effect import in `checks/__init__.py` to trigger registration
3. Add unit tests in `tests/unit/test_checks.py`

### `CheckStatus` values

The enum uses emoji as string values (`CheckStatus.COMPLIANT == "✅"`). Use the enum throughout — never hardcode emoji strings.

### File scanning utilities

- `find_regexp_in_path(path, pattern)` — searches git-tracked files only (falls back to all non-hidden files); skips files > 5 MiB and non-UTF-8 files
- `find_files_in_path(path, filename)` — finds files by name, git-tracked only
- `find_charmcraft_paths(path)` — finds `charmcraft.yaml` files, excluding `tests/` directories

### Copyright header

Every source file must start with:
```python
# Copyright <year> Canonical Ltd.
# See LICENSE file for licensing details.
```

Enforced by `ruff` (CPY rule, `flake8-copyright`). Ruff also enforces Google-style docstrings, line length 99, and the full ruleset configured in `pyproject.toml`.

### Test helpers

Unit tests use `_make_simple_check()` to create minimal `Check` subclasses dynamically. These are popped from `_REGISTRY` immediately to avoid polluting other tests. Always call `configure_checks({})` in `setup_method`/`teardown_method` when a test touches `_checks_overrides`.
