---
name: cli-vpn-install
description: Install or update a portable cross-platform OpenVPN command set backed by an encrypted bundle. Use when the user wants `cli-vpn-install`, `vpn`, or `voff` available on a macOS or Windows machine, wants to rebuild the encrypted VPN bundle, or needs to inspect or remove the local VPN runtime.
---

# CLI VPN Install

Use this skill to install a repo-managed VPN runtime onto the current machine and expose stable user commands:

- `cli-vpn-install install` — install runtime + config
- `cli-vpn-install status` — check connection state
- `cli-vpn-install uninstall` — remove everything
- `vpn` — connect
- `voff` — disconnect

The repo keeps only public-safe assets: an encrypted OpenVPN bundle plus structured whitelist and settings files. Plaintext `.ovpn`, auth material, decrypted configs, and locally persisted admin capability stay on the machine where the skill is installed.

## Quick Start (new machine)

### Prerequisites

- **OpenVPN** installed at `C:\Program Files\OpenVPN\bin\openvpn.exe` (Windows) or `/opt/homebrew/sbin/openvpn` (macOS)
- **Python 3** available on PATH
- **Admin / sudo** access (OpenVPN needs elevated privileges for TUN/DCO adapters and route tables)

### Windows

```powershell
# 1. Clone the repo
git clone https://github.com/liao1heng/destiny-skill.git D:\destiny-skill

# 2. Install with bundle passphrase (passphrase is "destiny")
$env:CLI_VPN_BUNDLE_PASSPHRASE = "destiny"
python D:\destiny-skill\skills\cli-vpn-install\scripts\cli_vpn_install.py install

# 3. Connect
vpn

# 4. Verify
cli-vpn-install status

# 5. Disconnect
voff
```

### macOS

```bash
git clone https://github.com/liao1heng/destiny-skill.git ~/destiny-skill
export CLI_VPN_BUNDLE_PASSPHRASE=destiny
python3 ~/destiny-skill/skills/cli-vpn-install/scripts/cli_vpn_install.py install
vpn
voff
```

## Bundle Passphrase

The encrypted bundle (`assets/vpn-bundle.enc.json`) contains the `.ovpn` config and `auth.txt` credentials.

- **Passphrase**: `destiny`
- Set via env var: `CLI_VPN_BUNDLE_PASSPHRASE=destiny`
- Or pass directly: `--bundle-passphrase destiny`

To rebuild the bundle (maintainer only):

```bash
python3 skills/cli-vpn-install/scripts/package_bundle.py \
  --ovpn-path /path/to/profile.ovpn \
  --auth-path /path/to/auth.txt \
  --passphrase destiny
```

## Windows Features

### Split Tunneling (route-nopull)

Only whitelisted destinations route through the VPN tunnel. All other traffic uses the local network.

- `settings.json` → `windows.route_nopull: true`
- OpenVPN launched with `--route-nopull`
- `.ovpn` injected with `route-nopull` + `pull-filter ignore "redirect-gateway"` at install time
- Whitelist defined in `assets/whitelist.json` (Google, GitHub, OpenAI, Cloudflare, DNS, etc.)

### DNS Anti-Poisoning

GFW poisons UDP port 53 DNS queries. Even with DNS set to 8.8.8.8, Windows system resolver receives forged responses. This skill applies a two-layer fix on connect:

1. **Primary DNS override** — sets the main adapter's DNS to `8.8.8.8` / `1.1.1.1` (both in whitelist, so DNS queries route through VPN)
2. **hosts file injection** — resolves whitelisted domains (Google, GitHub, OpenAI, Gemini, YouTube, etc.) via `nslookup <domain> 8.8.8.8` and writes real IPs to `C:\Windows\System32\drivers\etc\hosts`

On disconnect, both are restored (DNS reverted to original, hosts entries removed).

- `settings.json` → `windows.dns_fix: true`
- Domains list: `DNS_FIX_DOMAINS` in `cli_vpn_install.py`

### Google IPv6 Blocking

Three-layer blockade to prevent Google traffic from leaking via IPv6:

1. `.ovpn` injected with `pull-filter ignore "route-ipv6"` + `pull-filter ignore "ifconfig-ipv6"`
2. Tunnel adapter IPv6 binding disabled via `Disable-NetAdapterBinding -ComponentID ms_tcpip6`
3. Windows Firewall rules block 5 Google IPv6 CIDR ranges:
   - `2404:6800::/32`
   - `2600:1900::/28`
   - `2607:f8b0::/32`
   - `2800:3f0::/48`
   - `2a00:1450::/40`

- `settings.json` → `windows.disable_ipv6: true`, `windows.block_google_ipv6: true`

### Elevated Execution

All VPN operations run with admin privileges via Windows Scheduled Tasks:

| Task | RunLevel | Purpose |
|------|----------|---------|
| `CodexCliVpnInstallConnect` | Highest | Start OpenVPN, apply routes, disable IPv6, set DNS, refresh hosts |
| `CodexCliVpnInstallDisconnect` | Highest | Kill OpenVPN, remove routes, restore DNS, clean hosts |
| `CodexCliVpnInstallWatch` | Highest | Monitor tunnel health, auto-reconnect |

`vpn` / `voff` commands trigger these tasks, so no manual elevation is needed.

## Whitelist Domains (DNS Fix)

Domains resolved and written to hosts file on connect:

- Google: `www.google.com`, `google.com`, `accounts.google.com`, `accounts.google.com.sg`, `mail.google.com`, `drive.google.com`, `docs.google.com`, `gemini.google.com`
- YouTube: `www.youtube.com`, `youtube.com`
- GitHub: `github.com`, `api.github.com`, `raw.githubusercontent.com`, `gist.github.com`, `codeload.github.com`, `objects.githubusercontent.com`
- OpenAI: `api.openai.com`, `chat.openai.com`, `platform.openai.com`

## Workflow

1. Use `scripts/entry.sh` on macOS or `scripts/entry.ps1` on Windows to run install, status, or uninstall.
2. Use `scripts/package_bundle.py` only on a trusted maintainer machine when rebuilding the encrypted bundle from local plaintext VPN files.
3. After install, users call `vpn` to connect and `voff` to disconnect.

## Commands

```bash
bash skills/cli-vpn-install/scripts/entry.sh install
bash skills/cli-vpn-install/scripts/entry.sh status
bash skills/cli-vpn-install/scripts/entry.sh uninstall
python3 skills/cli-vpn-install/scripts/package_bundle.py --passphrase destiny
```

```powershell
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 install
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 status
pwsh -File skills/cli-vpn-install/scripts/entry.ps1 uninstall
py -3 skills/cli-vpn-install/scripts/package_bundle.py --passphrase destiny
```

## Notes

- `scripts/cli_vpn_install.py` is the single source of truth for install, runtime management, bundle decryption, watchers, and platform-specific helpers.
- `assets/whitelist.json` and `assets/settings.json` must stay platform-neutral because both macOS and Windows consume them.
- If the encrypted bundle changes, update it through the packaging script instead of committing plaintext VPN material.
- The bundle passphrase is `destiny`. Set `CLI_VPN_BUNDLE_PASSPHRASE=destiny` before running install.
