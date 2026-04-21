# destiny-skill

Mirror of the local Codex `skills/` directory.

## Layout

The repository keeps the same structure as the local skills directory:

```text
skills/
  .system/
  cli-arc/
  cli-des/
  cli-dev/
  cli-init/
  cli-pm/
  cli-sync/
  cli-test/
  figma/
```

Each skill directory may include:

- `SKILL.md`
- `agents/`
- `references/`
- `scripts/`
- `templates/`
- `assets/`

## Scope

This repository stores the actual skill content used by the local Codex setup,
including helper scripts, references, templates, and assets.

Transient cache files such as `__pycache__` and `*.pyc` are intentionally excluded.

## Sync

This repository is paired with the local `cli-sync` skill.

- Local skill path is resolved dynamically from `${CODEX_HOME}/skills`, or
  `~/.codex/skills` when `CODEX_HOME` is not set.
- Repository path is resolved dynamically:
- if the script is running inside a `destiny-skill` checkout, it uses that checkout
- if the current working directory is inside a matching checkout, it uses that checkout
- otherwise it uses `${CODEX_HOME}/repos/destiny-skill` and clones there automatically
- GitHub auth is auto-discovered from the current machine:
- existing git credentials
- `gh auth token`
- environment tokens such as `GITHUB_MCP_PAT`, `GH_TOKEN`, or `GITHUB_TOKEN`
- SSH if the checkout already uses an SSH origin

Examples:

```powershell
pwsh -File skills/cli-sync/scripts/entry.ps1 -Mode pull
pwsh -File skills/cli-sync/scripts/entry.ps1 -Mode push -Message "Sync local Codex skills"
```

```bash
bash skills/cli-sync/scripts/entry.sh --mode pull
bash skills/cli-sync/scripts/entry.sh --mode push --message "Sync local Codex skills"
```

To sync onto another machine, clone this repository and run `cli-sync` directly.
It will discover paths automatically and create a managed checkout when needed.
