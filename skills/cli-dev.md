---
name: cli-dev
description: Use only when the user explicitly wants a separate Codex CLI worker to implement code, refactor, or run a long development task in parallel. Best for detached/background coding jobs, usually in a separate git worktree, in any repository.
---

# CLI Dev

Use this skill to launch an external `codex exec` worker for implementation work. It is for cases where the current agent should keep moving while another Codex CLI process edits code in parallel.

The worker model is fixed to `gpt-5.3-codex`.

## When to use

- The user explicitly asks to use Codex CLI for development.
- You want a detached/background implementation worker.
- The task is large enough that a separate git worktree is safer than editing in the current workspace.
- You need persistent worker artifacts such as logs, JSON events, and the final message.

## Workflow

1. Prefer an isolated git worktree for every write-heavy worker. Use `scripts/new-git-worktree.ps1` before launching if the task could conflict with current edits.
2. Run `scripts/run-codex-dev.ps1` with `-Workdir` and `-Prompt`.
3. Add `-Wait` only when the current step is blocked on the worker result. Omit it to spawn a background process and continue local work.
4. Review the worker's `last-message.txt` and the diff in the target worktree before merging.

## Commands

Create an isolated worktree:

```powershell
cli-dev -Repo "D:\workspace\my-repo" -Branch "codex\feature-a" -Path "D:\workspace\my-repo-feature-a"
```

Launch a background implementation worker:

```powershell
cli-dev -Workdir "D:\workspace\my-repo-feature-a" -Name "feature-a" -Prompt "Implement the requested feature and run focused verification."
```

Launch and wait for completion:

```powershell
cli-dev -Workdir "D:\workspace\my-repo-feature-a" -Name "feature-a" -Prompt "Implement the requested feature and run focused verification." -Wait
```

## Artifacts

Each run writes to `$HOME\.codex\jobs\<name>\`:

- `prompt.txt` - full worker prompt
- `runner.ps1` - generated runner script
- `events.jsonl` - Codex JSON event stream
- `last-message.txt` - worker final answer
- `stderr.log` - warnings and errors

## Notes

- The script uses `codex -a never exec -s workspace-write -m gpt-5.3-codex --json`.
- It assumes `codex` and authentication are already configured on the machine.
- Keep prompts explicit about scope and verification. The worker is autonomous and will modify files in the target worktree.
- `cli-dev -Repo ... -Branch ... -Path ...` is a shortcut for creating a dedicated git worktree.
