---
name: cli-test
description: Use only when the user explicitly wants a separate Kimi CLI worker to review, test, or verify code. Best for detached/background QA runs, regression checks, and independent verification against a worktree, in any repository.
---

# CLI Test

Use this skill to launch an external `kimi --print` worker for verification work. It is for cases where the current agent wants an independent Kimi CLI pass focused on tests, review, and findings instead of implementation.

The worker has global browser validation support through:

- `chrome-devtools` MCP
- `playwright` MCP
- installed `playwright` CLI plus Chromium runtime

## When to use

- The user explicitly asks to use Kimi CLI for testing or verification.
- You want a detached/background QA worker.
- You need an independent review after another worker changed code.
- You want logs, JSON events, final findings, and a before/after git status check.

## Workflow

1. Prefer a clean or isolated worktree for verification. If needed, use `cli-dev -Repo ... -Branch ... -Path ...` to create one first.
2. Run `scripts/run-codex-test.ps1` with `-Workdir` and `-Prompt`.
3. Default to `-Sandbox read-only`. The Kimi wrapper treats it as intent in the prompt because Kimi CLI does not enforce Codex-style sandbox modes.
4. Add `-Wait` only when the current step is blocked on the result. Omit it to let the test worker run in the background.
5. Review `last-message.txt`. If `status-warning.txt` exists, the worker changed repo state and the result needs manual inspection.
6. For UI tasks, explicitly tell the worker to use Playwright MCP or browser MCP instead of reasoning from code alone. The wrapper injects Kimi MCP config for both `playwright` and `chrome-devtools` automatically.

## Commands

Launch a read-only verification worker:

```powershell
cli-test -Workdir "D:\workspace\my-repo-feature-a" -Name "verify-feature-a" -Prompt "Review the current changes, run the smallest useful verification, and report findings." -Wait
```

Allow writable temp files when needed:

```powershell
cli-test -Workdir "D:\workspace\my-repo-feature-a" -Name "verify-feature-a" -Prompt "Run the relevant tests for the current change and report regressions only." -Sandbox workspace-write
```

Force real browser validation:

```powershell
cli-test -Workdir "D:\workspace\my-repo-feature-a" -Name "verify-ui" -Prompt "Use Playwright MCP or browser MCP to validate the changed UI flow and report only concrete failures." -Sandbox workspace-write -Wait
```

## Artifacts

Each run writes to `$HOME\.codex\jobs\<name>\`:

- `prompt.txt` - full worker prompt
- `runner.ps1` - generated runner script
- `before-status.txt` - git status before running
- `after-status.txt` - git status after running
- `status-warning.txt` - created only when repo status changed
- `events.jsonl` - Codex JSON event stream
- `last-message.txt` - worker final answer
- `stderr.log` - warnings and errors

## Notes

- The script uses `kimi --print --output-format stream-json`.
- The wrapper prompt tells the worker not to modify repo files. `-Sandbox` is advisory text for Kimi, not a hard sandbox.
- If tests need writable temp outputs, use a disposable worktree plus `-Sandbox workspace-write`.
