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

- Pull flow: `git pull` in `D:\workspace\sefe_dev\destiny-skill`, then mirror the
  managed skill folders into `C:\Users\the5010_566029155562\.codex\skills`.
- Push flow: mirror the managed local skill folders back into this repository,
  commit, and `git push`.
- Local GitHub auth is stored outside the repository in
  `C:\Users\the5010_566029155562\.codex\cli-sync\auth.ps1`.

To sync onto another machine, clone this repository, install the `cli-sync`
skill, and provide a local auth file at the same path.
