---
name: fix-quality-indicator
description: >-
  Use when asked to fix repositories failing a specific repolint quality
  indicator/check (e.g. "fix repos failing charmlibs", "open PRs for
  use_gh_runners", "remediate the ck8s check across failing repos").
  Finds every repo where the indicator is non-compliant in
  reports/quality.json, then walks through each one — reusing its existing
  clone under /tmp/repo_clones, applying a fix on a fix/<indicator> branch,
  getting the user's review, and opening a PR — one repository at a time.
---

# Fix a repolint quality indicator across failing repositories

This skill turns a failing repolint check into a batch of reviewed,
individually-approved pull requests — one per non-compliant repository. It
does **not** modify the `repolint` package itself; it only reads the report
`repolint` already produced and drives `git`/`gh` directly.

Everything mechanical (parsing the report, listing failing repos) is
delegated to the bundled script `scripts/list_failing_repos.py` so that step
is deterministic. Everything that requires judgement (understanding what the
check wants, writing the actual fix, drafting the PR body) is done by you,
the agent, following the steps below.

## Inputs

The user gives you a **quality indicator** — a repolint check name, e.g.
`charmlibs`, `use_gh_runners`, `ck8s`, `github_codeowners`. If they use a
loose description instead of the exact check name, resolve it against
`src/repolint/checks/*.py` (the `name = "..."` class attribute) or
`reports/quality.json`'s `metadata.checks` before continuing. If you can't
confidently resolve it, ask the user to confirm the exact check name.

## Step 1 — List failing repositories

Run the bundled helper (stdlib only, no repolint install required):

```bash
python3 .github/skills/fix-quality-indicator/scripts/list_failing_repos.py <indicator> \
  --report reports/quality.json
```

This prints one `org/repo` per line for every repository whose result for
`<indicator>` is ❌ (NOT_COMPLIANT). It exits non-zero with a clear message
if the report is missing or the indicator name is unknown — surface that
error to the user rather than guessing.

If there are zero failing repos, tell the user and stop.

## Step 2 — Understand what "compliant" means

Read `src/repolint/checks/<indicator>.py` (its `run()` method and
docstrings/description) to know exactly what the check validates. Also check
the per-repo `message` field in `reports/quality.json` for each failing repo
(`results.<repo>.<indicator>.message`) — it often states precisely what's
missing for that repo.

## Step 3 — Process each failing repo, one at a time

Do **not** batch this across repos. Fully finish (fix, review, push, PR — or
explicit skip) one repository before starting the next.

For each `org/repo`:

1. **Locate/prepare the clone.** Repolint clones repos to
   `/tmp/repo_clones/<org>_<repo>` (slashes replaced with underscores) when
   generating the report. Reuse it:
   ```bash
   clone_dir="/tmp/repo_clones/$(echo "org/repo" | tr / _)"
   ```
   If it doesn't exist for some reason, clone it fresh:
   `gh repo clone org/repo "$clone_dir" -- --depth 1`.

2. **Reset to a clean base.** The clone may be stale or have leftover state
   from report generation:
   ```bash
   git -C "$clone_dir" fetch origin
   default_branch=$(gh repo view org/repo --json defaultBranchRef --jq .defaultBranchRef.name)
   git -C "$clone_dir" checkout "$default_branch"
   git -C "$clone_dir" reset --hard "origin/$default_branch"
   git -C "$clone_dir" clean -fd
   ```

3. **Check for an existing PR first**, to avoid duplicating work:
   ```bash
   gh pr list --repo org/repo --head "fix/<indicator>" --state open --json url
   ```
   If one exists, report its URL to the user and **skip** this repo (move to
   the next one) rather than creating a duplicate.

4. **Create the branch**:
   ```bash
   git -C "$clone_dir" checkout -b "fix/<indicator>"
   ```
   (If it already exists locally from a previous run, check it out instead
   and confirm with the user whether to reuse or reset it.)

5. **Apply the fix.** Edit exactly what's needed to satisfy the check for
   this repo — nothing unrelated. Use the check's `run()` logic from Step 2
   as the source of truth for what "compliant" requires.

6. **Show the diff and wait for approval — every time, no exceptions.**
   ```bash
   git -C "$clone_dir" status
   git -C "$clone_dir" diff
   ```
   Present this to the user and ask them to approve, request changes, or
   skip this repo. If they request changes, apply them and show the diff
   again. **Never push or open a PR without explicit approval for that
   specific repo.**

7. **On approval — commit, push, open the PR:**
   ```bash
   git -C "$clone_dir" add -A
   git -C "$clone_dir" commit -m "chore: <indicator>" -m "<short explanation of the fix>"
   git -C "$clone_dir" push -u origin "fix/<indicator>"
   gh pr create --repo org/repo \
     --title "chore: <indicator>" \
     --body "Fixes the repolint '<indicator>' check: <short explanation>." \
     --head "fix/<indicator>"
   ```
   If the push fails (e.g. no write access), report the error to the user
   and move on to the next repo — do not attempt to fork; that's out of
   scope for this skill.

8. **On skip/reject**, note the reason and move to the next repo without
   pushing anything.

## Step 4 — Summarize

After all failing repos have been processed, present a summary table:

| Repository | Outcome |
|---|---|
| org/repo-a | PR opened: <url> |
| org/repo-b | Skipped: existing open PR <url> |
| org/repo-c | Skipped: push failed (no write access) |

## Guardrails

- Never force-push.
- Never touch files unrelated to the indicator's fix.
- Never batch-approve — each repo's diff must be individually reviewed.
- Don't modify `repolint`'s own source, tests, or `reports/quality.json` as
  part of "fixing" a repo (unless the target repo *is* this repolint repo
  itself).
