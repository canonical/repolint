# repolint

A repository compliance dashboard.

`repolint` analyses GitHub repositories against a set of engineering standards and
produces Markdown and JSON reports showing which repositories are compliant, which
are not, and why.

## Requirements

- Python ≥ 3.12
- [`gh`](https://cli.github.com/) CLI, authenticated (`gh auth login`)

### GitHub token permissions

`repolint` works with a fine-grained personal access token that has **read-only** access to the following permissions:

| Permission | Reason |
| --- | --- |
| **Administration** | Read branch-protection rules and required status checks |
| **Contents** | Read repository file tree and file contents |
| **Metadata** | Read basic repository metadata and topics |

To use a fine-grained token, authenticate with:

```bash
gh auth login --with-token <<< "<your-token>"
```

## Installation

Install directly from this repository using `uv`:

```bash
uv tool install git+ssh://git@github.com/canonical/repolint.git
```

## Usage

```bash
repolint [REPO] [--config PATH] [--query QUERY] ...
```

| Option | Default | Description |
| --- | --- | --- |
| `REPO` | _(none)_ | GitHub repository full name (`owner/repo`). Shorthand for analysing a single repository — no config file needed. Cannot be combined with `--query`. |
| `--config PATH` | `repolint.yaml` | Path to the YAML configuration file. Optional when `--query` or `REPO` is used. |
| `--query QUERY` | _(none)_ | GitHub search query; results merged with config repositories. Archived repos are excluded automatically. |
| `--output NAME` | `quality` | Base name for the summary reports: `NAME.json` and `NAME.md`. Per-repository detail files are always named `<org>-<repo>-details.md`. |
| `--output-dir DIR` | `reports` | Directory where all report files are written. Created if it does not exist. |
| `--version` | — | Print the installed version and exit. |

### Examples

```bash
# Analyse the repository in the current working directory (auto-detected from git remote).
# Uses the local working tree directly — no network clone needed.
# The detail report is shown in the terminal immediately; no files written to the CWD.
repolint

# Analyse a specific repository by name — no config file needed
repolint canonical/my-charm

# Pass a GitHub search query directly — no config file needed
repolint --query "org:canonical topic:platform-engineering topic:squad-emea"

# Analyse repositories listed in repolint.yaml (current directory)
repolint --config repolint.yaml

# Use a custom configuration file
repolint --config ~/my-repos.yaml

# Combine a query with a config file (results merged, duplicates removed)
repolint --config ~/my-repos.yaml --query "org:canonical topic:platform-engineering"
```

### Sample session

[![asciicast](https://asciinema.org/a/AJbj238wZTOR6SJN.svg)](https://asciinema.org/a/AJbj238wZTOR6SJN)

### Output

Reports are written to a `reports/` directory in the working directory:

| File | Contents |
| --- | --- |
| `reports/quality.md` | Markdown table — one row per repository, one column per visible check |
| `reports/quality.json` | Raw JSON results for all checks |

> **Tip:** Preview Markdown locally with `repolint --show-report [path-to-markdown]`

## Configuration

Create a `repolint.yaml` file **in the directory where you run the command**.
At least one of `repositories` or `repository_query` must be present.

### Static repository list

```yaml
repositories:
  - canonical/my-charm
  - canonical/another-charm
  - canonical/yet-another-charm
```

Each entry is a fully-qualified GitHub repository name in `org/repo` format.

### Dynamic query

```yaml
repository_query: "org:canonical topic:platform-engineering topic:squad-emea"
```

The query is passed directly to `gh search repos`.  `archived:false` is
automatically appended, so archived repositories are never included.
Results are merged with any repositories listed under `repositories`.

Both keys can be used together; the final list is deduplicated while preserving
order (static list first, then query results).

### Combining both

```yaml
repositories:
  - canonical/special-repo    # always included

repository_query: "org:canonical topic:platform-engineering"
```

### Excluding repositories from specific checks

Individual repositories can be excluded from a check via the `checks` key:

```yaml
repositories:
  - canonical/my-charm

checks:
  github_topics:
    excluded:
      - canonical/my-charm   # this repo doesn't need the standard topics
  github2jira:
    excluded:
      - canonical/my-charm   # no Jira integration required
  codeowners:
    excluded:
      - canonical/my-charm   # no CODEOWNERS required
    valid_patterns:
      - "@canonical/my-team$"
    invalid_patterns:
      - "@individual-username"
```

> A missing CODEOWNERS file is reported as ❌ unless the repository is
> excluded. At least one of `valid_patterns` must match a non-comment line;
> `invalid_patterns` must not match any line.

> Excluded repositories are reported as ➖ for that check, distinct from `n/a`
> (a dependency check was not met).

## Checks

Each repository is evaluated against the following criteria.
Results are cached in `reports/quality.json` so subsequent runs only re-run
checks for repositories that are new or whose set of checks has changed.
Repositories removed from the configuration are dropped from the report
automatically.

### Overview checks (shown in the overview table)

| Check | Description |
| --- | --- |
| `github` | Repository matches all GitHub best practices (topics, Jira integration, required status checks) |
| `dependencies` | Repository uses charmlibs instead of deprecated `operator_libs_linux` |
| `unit_tests` | Repository follows unit testing best practices (no Harness) |
| `integration_tests` | Repository follows integration testing best practices (Jubilant, Juju 4, CK8s) |
| `terraform` | Repository follows Terraform best practices (Juju provider v1) |

### Sub-checks (hidden in the overview, visible in per-repository detail reports)

| Check | Parent | Description |
| --- | --- | --- |
| `github_topics` | `github` | Repository has a topic matching every configured pattern (see `checks.github_topics.patterns`) |
| `github2jira` | `github` | `.github/.jira_sync_config.yaml` is present |
| `codeowners` | `github` | A CODEOWNERS file exists and matches configured patterns (see `checks.codeowners.valid_patterns` / `invalid_patterns`) |
| `github_required_checks` | `github` | The default branch has at least one required status check |
| `charmlibs` | `dependencies` | No imports of the deprecated `charms.operator_libs_linux` |
| `ops_testing` | `unit_tests` | No references to the deprecated Harness testing API |
| `jubilant` | `integration_tests` | Integration tests use Jubilant |
| `juju4` | `integration_tests` | At least one workflow targets Juju 4/stable |
| `ck8s` | `integration_tests` | GitHub workflows set `use-canonical-k8s: true` |
| `tf_v1` | `terraform` | All `versions.tf` files pin Juju provider `~> 1.*` |
| `contains_charm` | _(internal)_ | Repository contains at least one `charmcraft.yaml` |
| `contains_k8s_charm` | _(internal)_ | Repository contains at least one Kubernetes charm |

### Check result symbols

| Symbol | Meaning |
| --- | --- |
| ✅ | Compliant |
| ❌ | Not compliant |
| ⚠️ | Could not be checked (e.g. network/auth error or insufficient permissions) |
| n/a | Not eligible — a dependency check is not met, so this check does not apply |
| ➖ | Excluded — the repository is explicitly excluded from this check in the config |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, project layout,
and instructions for adding new checks.
