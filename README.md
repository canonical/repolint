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

### Excluding repositories from specific checks

Individual repositories can be excluded from a check via the `checks` key:

```yaml
repositories:
  - canonical/my-charm

checks:
  pfe_topic:
    excluded:
      - canonical/my-charm   # this repo doesn't need the pfe topic
  github2jira:
    excluded:
      - canonical/my-charm   # no Jira integration required
```

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
Results are cached in `reports/quality.json` so subsequent runs only re-run
checks for repositories that have not been analysed yet.

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

### Check result symbols

| Symbol | Meaning |
|---|---|
| ✅ | Compliant |
| ❌ | Not compliant |
| n/a | Not eligible (dependency not met, or repository explicitly excluded) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, project layout,
and instructions for adding new checks.
