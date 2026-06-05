# Changelog

## [0.7.0] - 2026-04-22

### Added

- **Shortcut mode** (running `repolint` with no arguments from inside a git repository):
  - The local working tree is used directly instead of cloning the repository from GitHub — faster and works offline for file-based checks.
  - Reports are written to a temporary directory instead of `reports/` in the current folder.
  - The per-repository detail report is displayed in the terminal immediately after analysis.
- **`.gitignore`-aware scanning**: file-based checks (`ops_testing`, `charmlibs`, `github2jira`, `ck8s`, `tf_v1`, `contains_charm`, `contains_k8s_charm`, `jubilant`, `juju4`) now use `git ls-files` to restrict scanning to tracked files only, avoiding false positives from `.venv/`, `node_modules/`, `__pycache__/`, and other gitignored artefacts.
- **`--version`** flag: `repolint --version` prints the installed version.

## [0.6.0] - 2026-04-22

### Added

- `repolint` with no arguments now auto-detects the GitHub repository from the current working directory's `origin` git remote and analyses it directly.
- `repolint <owner/repo>` positional shorthand: pass a repository full name to analyse it without a config file.
- Unit tests run automatically on `git push` via a new `pre-push` hook in `.pre-commit-config.yaml` (activate with `pre-commit install --hook-type pre-push`).

## [0.5.0] - 2026-04-17

### Added

- Detailed report for each subchecks.


## [0.4.0] - 2026-04-15

### Added

- New check `github_required_checks`: ensures the default branch has required status checks configured in branch protection rules. Belongs to the `github` check group.

## [0.3.0]

- Previous release.
