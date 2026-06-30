---
name: cli-vpn-install
description: Install or update a portable cross-platform OpenVPN command set backed by an encrypted bundle. Use when the user wants `cli-vpn-install`, `vpn`, or `voff` available on a macOS or Windows machine, wants to rebuild the encrypted VPN bundle, or needs to inspect or remove the local VPN runtime.
---

# CLI VPN Install

Use this skill to install a repo-managed VPN runtime onto the current machine and expose stable user commands:

- `cli-vpn-install install`
- `cli-vpn-install status`
- `cli-vpn-install uninstall`
- `vpn`
- `voff`

The repo keeps only public-safe assets: an encrypted OpenVPN bundle plus structured whitelist and settings files. Plaintext `.ovpn`, auth material, decrypted configs, and locally persisted admin capability stay on the machine where the skill is installed.

## Workflow

1. Use `scripts/entry.sh` on macOS or `scripts/entry.ps1` on Windows to run install, status, or uninstall.
2. Use `scripts/package_bundle.py` only on a trusted maintainer machine when rebuilding the encrypted bundle from local plaintext VPN files.
3. After install, users call `vpn` to connect and `voff` to disconnect.

## Commands

```bash
bash skills/cli-vpn-install/scripts/entry.sh install
bash skills/cli-vpn-install/scripts/entry.sh status
bash skills/cli-vpn-install/scripts/entry.sh uninstall
python3 skills/cli-vpn-install/scripts/package_bundle.py --passphrase-env CLI_VPN_BUNDLE_PASSPHRASE
```

```powershell
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 install
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 status
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 uninstall
py -3 skills/cli-vpn-install/scripts/package_bundle.py --passphrase-env CLI_VPN_BUNDLE_PASSPHRASE
```

## Notes

- `scripts/cli_vpn_install.py` is the single source of truth for install, runtime management, bundle decryption, watchers, and platform-specific helpers.
- `assets/whitelist.json` and `assets/settings.json` must stay platform-neutral because both macOS and Windows consume them.
- If the encrypted bundle changes, update it through the packaging script instead of committing plaintext VPN material.
