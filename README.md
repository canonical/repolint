# repolint

A repository compliance dashboard for Canonical Platform Engineering.

`repolint` analyses GitHub repositories against a set of engineering standards and
produces Markdown and JSON reports showing which repositories are compliant, which
are not, and why.

## Requirements

- Python ≥ 3.12
- [`gh`](https://cli.github.com/) CLI, authenticated (`gh auth login`)

## Installation

Install directly from this repository using `uv`:

```bash
uv add git+https://github.com/canonical/repolint
```

Or with pip:

```bash
pip install git+https://github.com/canonical/repolint
```

## Configuration

`repolint` reads repository lists from a `config/` directory **in the working
directory where you run the command**. Create one file per squad:

```
config/
├── squad-repos.americas.txt
├── squad-repos.apac.txt
└── squad-repos.emea.txt
```

Each file contains one fully-qualified GitHub repository name per line:

```
canonical/my-charm
canonical/another-charm
```

When using the `all` scope, `repolint` reads each squad file in turn and merges
the results.

## Usage

```
repolint <scope>
```

| Scope | Description |
|---|---|
| `all` | Analyse every repository across all squads |
| `americas` / `apac` / `emea` | Analyse repositories for a single squad |
| `canonical/repo-name` | Debug a single repository (prints JSON + Markdown to stdout) |

### Examples

```bash
# Analyse all squads
repolint all

# Analyse one squad
repolint apac

# Debug a single repository
repolint canonical/my-charm
```

### Output

Reports are written to a `reports/` directory in the working directory:

| File | Contents |
|---|---|
| `reports/quality-<squad>.md` | Markdown table — one row per repository, one column per visible check |
| `reports/quality-<squad>.json` | Raw JSON results for all checks |
| `reports/quality-<repo>-details.md` | Per-repository detail report |
| `reports/quality-all.md` | Combined table across all squads (only with `all` scope) |

> **Tip:** Preview Markdown locally with `pip install grip && grip reports/quality-all.md`

#### Caching

If a `quality-<squad>.json` file already exists, `repolint` reuses it instead of
re-running the analysis. Delete the file to force a fresh run:

```bash
rm reports/quality-apac.json && repolint apac
```

## Checks

Each repository is evaluated against the following criteria.

### Aggregate checks (shown in the overview table)

| Check | Description |
|---|---|
| `github` | Repository matches all GitHub best practices (topics + Jira integration) |
| `charmlibs` | Repository uses charmlibs instead of `operator_libs_linux` |
| `unit_tests` | Repository follows unit testing best practices (no Harness) |
| `integration_tests` | Repository follows integration testing best practices (Jubilant, Juju 4, CK8s) |
| `terraform` | Repository follows Terraform best practices (Juju provider v1) |

### Sub-checks (hidden in the overview, visible in per-repository detail reports)

| Check | Description |
|---|---|
| `pfe_topic` | Repository has the `platform-engineering` GitHub topic |
| `squad_topic` | Repository has a `squad-*` GitHub topic |
| `product_topic` | Repository has a `product-*` GitHub topic |
| `github2jira` | `.github/.jira_sync_config.yaml` is present |
| `contains_charm` | Repository contains at least one `charmcraft.yaml` |
| `contains_k8s_charm` | Repository contains at least one Kubernetes charm |
| `ops_testing` | No references to the deprecated Harness testing API |
| `jubilant` | Integration tests use Jubilant |
| `juju4` | At least one workflow targets Juju 4/stable |
| `ck8s` | GitHub workflows set `use-canonical-k8s: true` |
| `tf_v1` | All `versions.tf` files pin Juju provider `~> 1.*` |

## Development

Clone the repository and install the development tooling:

```bash
git clone https://github.com/canonical/repolint
cd repolint
uv sync --all-groups
```

### Running checks

```bash
tox -e lint      # codespell + ruff + mypy
tox -e unit      # pytest + coverage
tox -e static    # bandit (medium+ severity)
tox -e fmt       # auto-format with ruff
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

### Project layout

```
src/repolint/
├── config.py      # Constants (squad names, check symbols, paths)
├── criteria.py    # Check catalogue — add new checks here
├── checks.py      # @check decorator, registry, check implementations
├── report.py      # Report rendering and analysis orchestration
├── __main__.py    # CLI entry point
tests/unit/        # Unit tests (pytest)
config/            # Repository lists (not committed — add your own)
reports/           # Generated reports (git-ignored)
```

### Adding a new check

1. Add an entry to `list_criteria()` in `src/repolint/criteria.py`.
2. Implement `check_repository_<name>()` in `src/repolint/checks.py`, decorated
   with `@check`.
3. If the new check is an aggregate of existing sub-checks, set `"aggregates"` in
   the criteria entry and use `aggregate_check` as the implementation — no
   function body needed.
4. Add unit tests in `tests/unit/`.
