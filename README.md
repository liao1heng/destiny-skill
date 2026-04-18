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
  cli-pm/
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

To sync onto another machine, clone this repository and copy `skills/` into the
target Codex home directory.
