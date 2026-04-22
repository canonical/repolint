# Changelog

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
