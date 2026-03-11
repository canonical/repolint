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

Create a `repolint.yaml` file **in the directory where you run the command**:

```yaml
repositories:
  - canonical/my-charm
  - canonical/another-charm
  - canonical/yet-another-charm
```

Each entry is a fully-qualified GitHub repository name in `org/repo` format.

A different config file can be passed via the `--config` flag (see [Usage](#usage)).

## Usage

```bash
repolint [--config PATH]
```

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `repolint.yaml` | Path to the YAML configuration file |

### Examples

```bash
# Analyse repositories listed in repolint.yaml (current directory)
repolint

# Use a custom configuration file
repolint --config ~/my-repos.yaml

# Use a config file in another directory
repolint --config /path/to/project/repolint.yaml
```

### Output

Reports are written to a `reports/` directory in the working directory:

| File | Contents |
|---|---|
| `reports/quality.md` | Markdown table — one row per repository, one column per visible check |
| `reports/quality.json` | Raw JSON results for all checks |

> **Tip:** Preview Markdown locally with `pip install grip && grip reports/quality.md`

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
├── config.py      # Constants (check symbols, paths, defaults)
├── criteria.py    # Check catalogue — add new checks here
├── checks.py      # @check decorator, registry, check implementations
├── report.py      # Report rendering and analysis orchestration
├── __main__.py    # CLI entry point
tests/unit/        # Unit tests (pytest)
repolint.yaml      # Repository list (create your own — not committed)
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
