---
name: cli-mimo
description: Use only when the user explicitly wants a separate Claude Code CLI worker backed by Xiaomi MiMo for development, testing, verification, or review. Best for detached or blocking jobs that should run in another worktree or as a dedicated MiMo-based worker in any repository.
---

# CLI MiMo

Use this skill to launch an external `claude` worker that runs through the globally configured Xiaomi MiMo endpoint.

The worker assumes MiMo is already configured in the user's Claude Code settings or user environment. Use `cli-mimo -Healthcheck` before longer jobs when connectivity is uncertain.

## Workflow

1. Prefer an isolated git worktree for write-heavy jobs. Use `cli-mimo -Repo ... -Branch ... -Path ...` first when the task could conflict with current edits.
2. Use `-Mode dev` for implementation work. Its default sandbox intent is `workspace-write`.
3. Use `-Mode test` for review, regression checks, or independent verification. Its default sandbox intent is `read-only`, but the wrapper enforces this only through the worker prompt and git-status checks.
4. Add `-Wait` when the current step is blocked on the worker result. Omit it to run in the background and review artifacts later.
5. Review `last-message.txt` and `stderr.log` after each run. If `status-warning.txt` exists, inspect the worktree before trusting a test result.

## Commands

Health check:

```powershell
cli-mimo -Healthcheck
```

Create an isolated worktree:

```powershell
cli-mimo -Repo "D:\workspace\my-repo" -Branch "codex\feature-a" -Path "D:\workspace\my-repo-feature-a"
```

Launch a development worker and wait:

```powershell
cli-mimo -Mode dev -Workdir "D:\workspace\my-repo-feature-a" -Name "feature-a" -Prompt "Implement the requested feature and run focused verification." -Wait
```

Launch a test worker in the background:

```powershell
cli-mimo -Mode test -Workdir "D:\workspace\my-repo-feature-a" -Name "verify-feature-a" -Prompt "Review the current changes, run the smallest useful verification, and report concrete findings only."
```

## Artifacts

Each run writes to `$HOME\.codex\jobs\<name>\`:

- `prompt.txt` - full worker prompt
- `runner.ps1` - generated runner script
- `before-status.txt` - git status before running, when inside a git repo
- `after-status.txt` - git status after running, when inside a git repo
- `status-warning.txt` - created when repo status changed during the run
- `last-message.txt` - worker final answer
- `stderr.log` - warnings and errors

## Notes

- The wrapper uses `claude -p --permission-mode bypassPermissions --no-session-persistence`.
- It injects `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, and model defaults from the user environment before launching Claude so the MiMo route is deterministic.
- `-Sandbox` is intent, not a real process sandbox. Use disposable worktrees when you need stronger isolation.
