#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


APP_NAME = "cli-vpn-install"
APP_VERSION = 1
KEYCHAIN_SERVICE = "cli-vpn-install/sudo"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
STREAM_NONCE_BYTES = 16
WRAPPER_MARKER_START = "# >>> cli-vpn-install >>>"
WRAPPER_MARKER_END = "# <<< cli-vpn-install <<<"
WINDOWS_TASK_SCRIPT = "vpn_task.ps1"
WINDOWS_REGISTER_SCRIPT = "register_tasks.ps1"
WINDOWS_UNREGISTER_SCRIPT = "unregister_tasks.ps1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def home_dir() -> Path:
    return Path.home().resolve()


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (home_dir() / ".codex").resolve()


def install_root() -> Path:
    return codex_home() / "vpn"


def runtime_root() -> Path:
    return install_root() / "runtime"


def config_root() -> Path:
    return install_root() / "config"


def state_root() -> Path:
    return install_root() / "state"


def logs_root() -> Path:
    return install_root() / "logs"


def wrapper_root() -> Path:
    return codex_home() / "bin"


def state_path() -> Path:
    return state_root() / "state.json"


def openvpn_pid_path() -> Path:
    return state_root() / "openvpn.pid"


def openvpn_log_path() -> Path:
    return logs_root() / "openvpn.log"


def watch_log_path() -> Path:
    return logs_root() / "watch.log"


def local_bundle_manifest_path() -> Path:
    return install_root() / "bundle-manifest.json"


def source_script_dir() -> Path:
    return Path(__file__).resolve().parent


def source_skill_root() -> Path:
    return source_script_dir().parent


def source_asset_dir() -> Path:
    return source_skill_root() / "assets"


def resolve_asset_path(name: str) -> Path:
    runtime_candidate = source_script_dir() / name
    if runtime_candidate.exists():
        return runtime_candidate
    source_candidate = source_asset_dir() / name
    if source_candidate.exists():
        return source_candidate
    raise FileNotFoundError(f"Missing required asset: {name}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_install_dirs() -> None:
    for path in (runtime_root(), config_root(), state_root(), logs_root(), wrapper_root()):
        path.mkdir(parents=True, exist_ok=True)


def set_owner_only_permissions(path: Path) -> None:
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_state() -> dict:
    path = state_path()
    if not path.exists():
        return {
            "version": APP_VERSION,
            "platform": platform.system(),
            "installed_at": None,
            "updated_at": None,
            "connected": False,
            "openvpn_pid": None,
            "watcher_pid": None,
            "tunnel_interface": None,
            "tunnel_ip": None,
            "applied_routes": [],
            "pre_connect": {},
        }
    return read_json(path)


def save_state(state: dict) -> None:
    state["version"] = APP_VERSION
    state["platform"] = platform.system()
    state["updated_at"] = utc_now()
    write_json(state_path(), state)


def log_watch(message: str) -> None:
    ensure_parent(watch_log_path())
    with watch_log_path().open("a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def _decode_subprocess_output(data) -> str:
    """Decode subprocess output bytes to str, handling mixed encodings on Windows.

    On Windows, command output may be UTF-8 (PowerShell with UTF-8 output) or
    GBK/cp936 (legacy console commands like schtasks, ipconfig). We try UTF-8
    first, then fall back to the system locale encoding.
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    for encoding in ("utf-8", "gbk", "cp936", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def run_command(
    command: list[str],
    *,
    input_text: str | None = None,
    capture_output: bool = True,
    check: bool = False,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    if is_windows():
        # On Windows, avoid text=True because the system locale (GBK on Chinese
        # Windows) may not match the actual output encoding of commands like
        # PowerShell (UTF-8). Capture raw bytes and decode defensively.
        result = subprocess.run(
            command,
            input=input_text.encode("utf-8") if input_text else None,
            capture_output=capture_output,
            check=False,
            env=env,
            timeout=timeout,
        )
        stdout = _decode_subprocess_output(result.stdout)
        stderr = _decode_subprocess_output(result.stderr)
        return subprocess.CompletedProcess(
            args=result.args,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=capture_output,
        check=False,
        env=env,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed ({' '.join(command)}): {stderr}")
    return result


def command_output(command: list[str], *, check: bool = True) -> str:
    result = run_command(command, check=check)
    return result.stdout.strip()


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def which_python() -> list[str]:
    for candidate in ("python3", "python"):
        path = shutil.which(candidate)
        if path:
            return [path]
    if is_windows():
        py_path = shutil.which("py")
        if py_path:
            return [py_path, "-3"]
    raise RuntimeError("Python 3 is required but was not found in PATH.")


def ensure_openvpn_binary() -> str:
    path = find_openvpn_binary()
    if path:
        return path
    if is_macos():
        raise RuntimeError(
            "OpenVPN CLI was not found. Install it first, for example with `brew install openvpn`."
        )
    if is_windows():
        raise RuntimeError(
            "openvpn.exe was not found. Install OpenVPN Community and ensure openvpn.exe is available."
        )
    raise RuntimeError("Unsupported platform. cli-vpn-install currently supports macOS and Windows only.")


def find_openvpn_binary() -> str | None:
    candidate = shutil.which("openvpn")
    if candidate:
        return candidate
    if is_macos():
        for path in (
            "/opt/homebrew/sbin/openvpn",
            "/usr/local/sbin/openvpn",
            "/usr/sbin/openvpn",
        ):
            if Path(path).exists():
                return path
        return None
    if is_windows():
        candidate = shutil.which("openvpn.exe")
        if candidate:
            return candidate
        roots = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "OpenVPN" / "bin" / "openvpn.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "OpenVPN" / "bin" / "openvpn.exe",
        ]
        for path in roots:
            if path.exists():
                return str(path)
    return None


def settings() -> dict:
    return read_json(resolve_asset_path("settings.json"))


def whitelist_routes() -> list[dict]:
    payload = read_json(resolve_asset_path("whitelist.json"))
    return list(payload["routes"])


def install_runtime_assets() -> list[Path]:
    ensure_install_dirs()
    copied: list[Path] = []
    source_files = [
        source_script_dir() / "cli_vpn_install.py",
        source_script_dir() / "entry.sh",
        source_script_dir() / "entry.ps1",
        source_asset_dir() / "settings.json",
        source_asset_dir() / "whitelist.json",
    ]
    optional_sources = [
        source_asset_dir() / "vpn-bundle.enc.json",
    ]
    for source in source_files + [path for path in optional_sources if path.exists()]:
        destination = runtime_root() / source.name
        shutil.copy2(source, destination)
        copied.append(destination)
    for path in copied:
        if path.name.endswith(".py") or path.name.endswith(".sh"):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
    if is_windows():
        write_windows_support_scripts()
    return copied


def write_windows_support_scripts() -> None:
    if not is_windows():
        return
    task_script = runtime_root() / WINDOWS_TASK_SCRIPT
    register_script = runtime_root() / WINDOWS_REGISTER_SCRIPT
    unregister_script = runtime_root() / WINDOWS_UNREGISTER_SCRIPT

    # Embed the Python executable path used during install so the scheduled
    # task does not rely on PATH lookup (which may fail in the task's context
    # when Python is installed in a non-standard location like a managed
    # runtime directory).
    python_exe = sys.executable.replace("\\", "\\\\")

    task_script.write_text(
        f"""param([Parameter(Mandatory = $true)][string]$Action)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Preferred Python path (embedded during install)
$preferredPython = '{python_exe}'

$pythonCommand = $null
if (Test-Path $preferredPython) {{
    $pythonCommand = $preferredPython
}}
if (-not $pythonCommand) {{
    foreach ($candidate in @('py', 'python', 'python3')) {{
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {{
            $pythonCommand = $command.Source
            break
        }}
    }}
}}

if (-not $pythonCommand) {{
    throw 'Python 3 is required for cli-vpn-install.'
}}

$scriptPath = Join-Path $PSScriptRoot 'cli_vpn_install.py'
& $pythonCommand $scriptPath $Action
exit $LASTEXITCODE
""",
        encoding="utf-8",
    )

    register_script.write_text(
        f"""Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskRoot = $PSScriptRoot
$pyScript = Join-Path $taskRoot 'cli_vpn_install.py'
$pythonExe = '{python_exe}'
$taskPrefix = 'CodexCliVpnInstall'

function New-TaskAction([string]$ActionName) {{
    $arguments = "`"$pyScript`" $ActionName"
    New-ScheduledTaskAction -Execute $pythonExe -Argument $arguments
}}

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 12)

Register-ScheduledTask -TaskName ($taskPrefix + 'Connect') -Action (New-TaskAction 'elevated-connect') -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName ($taskPrefix + 'Disconnect') -Action (New-TaskAction 'elevated-disconnect') -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName ($taskPrefix + 'Watch') -Action (New-TaskAction 'watch-loop') -Principal $principal -Settings $settings -Force | Out-Null
""",
        encoding="utf-8",
    )

    unregister_script.write_text(
        """Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskPrefix = 'CodexCliVpnInstall'
foreach ($name in @($taskPrefix + 'Connect', $taskPrefix + 'Disconnect', $taskPrefix + 'Watch')) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}
""",
        encoding="utf-8",
    )


def create_unix_wrapper(command_name: str, action: str) -> None:
    wrapper = wrapper_root() / command_name
    code = f"""#!/usr/bin/env bash
set -euo pipefail
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    exec "$candidate" "{(runtime_root() / 'cli_vpn_install.py').as_posix()}" {action} "$@"
  fi
done
echo "Python 3 is required for cli-vpn-install." >&2
exit 1
"""
    wrapper.write_text(code, encoding="utf-8")
    wrapper.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def create_windows_wrapper(command_name: str, action: str) -> None:
    wrapper = wrapper_root() / f"{command_name}.cmd"
    script = f"""@echo off
setlocal
set "SCRIPT={runtime_root() / 'cli_vpn_install.py'}"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%SCRIPT%" {action} %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%SCRIPT%" {action} %*
  exit /b %ERRORLEVEL%
)
where python3 >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python3 "%SCRIPT%" {action} %*
  exit /b %ERRORLEVEL%
)
echo Python 3 is required for cli-vpn-install. 1>&2
exit /b 1
"""
    wrapper.write_text(script, encoding="utf-8")


def install_wrappers() -> None:
    ensure_install_dirs()
    if is_windows():
        create_windows_wrapper("cli-vpn-install", "dispatch")
        create_windows_wrapper("vpn", "connect")
        create_windows_wrapper("voff", "disconnect")
    else:
        create_unix_wrapper("cli-vpn-install", "dispatch")
        create_unix_wrapper("vpn", "connect")
        create_unix_wrapper("voff", "disconnect")


def update_unix_path() -> list[Path]:
    changed: list[Path] = []
    block = (
        f"{WRAPPER_MARKER_START}\n"
        f'export PATH="{wrapper_root().as_posix()}:$PATH"\n'
        f"{WRAPPER_MARKER_END}\n"
    )
    for filename in (".zshrc", ".bashrc"):
        path = home_dir() / filename
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if WRAPPER_MARKER_START in content and WRAPPER_MARKER_END in content:
            continue
        if content and not content.endswith("\n"):
            content += "\n"
        path.write_text(content + block, encoding="utf-8")
        changed.append(path)
    return changed


def remove_unix_path_block() -> list[Path]:
    changed: list[Path] = []
    pattern = re.compile(
        re.escape(WRAPPER_MARKER_START) + r".*?" + re.escape(WRAPPER_MARKER_END) + r"\n?",
        re.DOTALL,
    )
    for filename in (".zshrc", ".bashrc"):
        path = home_dir() / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        updated = pattern.sub("", content)
        if updated != content:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)
    return changed


def update_windows_path() -> None:
    import winreg

    desired = str(wrapper_root())
    access = winreg.KEY_READ | winreg.KEY_WRITE
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, access) as key:
        current, _ = winreg.QueryValueEx(key, "Path") if value_exists(key, "Path") else ("", winreg.REG_EXPAND_SZ)
        parts = [segment for segment in current.split(";") if segment]
        lowered = {segment.lower() for segment in parts}
        if desired.lower() not in lowered:
            parts.append(desired)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))


def remove_windows_path() -> None:
    import winreg

    desired = str(wrapper_root()).lower()
    access = winreg.KEY_READ | winreg.KEY_WRITE
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, access) as key:
        if not value_exists(key, "Path"):
            return
        current, value_type = winreg.QueryValueEx(key, "Path")
        parts = [segment for segment in current.split(";") if segment and segment.lower() != desired]
        winreg.SetValueEx(key, "Path", 0, value_type, ";".join(parts))


def value_exists(key, value_name: str) -> bool:
    import winreg

    try:
        winreg.QueryValueEx(key, value_name)
        return True
    except FileNotFoundError:
        return False


def managed_config_path() -> Path:
    return config_root() / "destiny.ovpn"


def managed_auth_path() -> Path:
    return config_root() / "auth.txt"


def bundle_available() -> bool:
    try:
        resolve_asset_path("vpn-bundle.enc.json")
        return True
    except FileNotFoundError:
        return False


def config_installed() -> bool:
    return managed_config_path().exists() and managed_auth_path().exists()


def derive_bundle_keys(passphrase: str, salt: bytes, iterations: int) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=64)
    return material[:32], material[32:]


def stream_xor(data: bytes, key: bytes, nonce: bytes) -> bytes:
    output = bytearray(len(data))
    offset = 0
    counter = 0
    while offset < len(data):
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        chunk = data[offset : offset + len(block)]
        for index, byte in enumerate(chunk):
            output[offset + index] = byte ^ block[index]
        offset += len(chunk)
        counter += 1
    return bytes(output)


def encrypt_bytes_to_bundle(plaintext: bytes, passphrase: str) -> dict:
    salt = os.urandom(PBKDF2_SALT_BYTES)
    nonce = os.urandom(STREAM_NONCE_BYTES)
    enc_key, mac_key = derive_bundle_keys(passphrase, salt, PBKDF2_ITERATIONS)
    ciphertext = stream_xor(plaintext, enc_key, nonce)
    mac = hmac.new(
        mac_key,
        b"|".join(
            [
                b"cli-vpn-install",
                str(APP_VERSION).encode("ascii"),
                str(PBKDF2_ITERATIONS).encode("ascii"),
                salt,
                nonce,
                ciphertext,
            ]
        ),
        hashlib.sha256,
    ).digest()
    return {
        "version": APP_VERSION,
        "kdf": "pbkdf2-hmac-sha256",
        "iterations": PBKDF2_ITERATIONS,
        "cipher": "hmac-sha256-stream-xor",
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "mac_b64": base64.b64encode(mac).decode("ascii"),
    }


def decrypt_bundle_bytes(payload: dict, passphrase: str) -> bytes:
    if payload.get("version") != APP_VERSION:
        raise RuntimeError(f"Unsupported bundle version: {payload.get('version')}")
    salt = base64.b64decode(payload["salt_b64"])
    nonce = base64.b64decode(payload["nonce_b64"])
    ciphertext = base64.b64decode(payload["ciphertext_b64"])
    provided_mac = base64.b64decode(payload["mac_b64"])
    iterations = int(payload["iterations"])
    enc_key, mac_key = derive_bundle_keys(passphrase, salt, iterations)
    expected_mac = hmac.new(
        mac_key,
        b"|".join(
            [
                b"cli-vpn-install",
                str(payload["version"]).encode("ascii"),
                str(iterations).encode("ascii"),
                salt,
                nonce,
                ciphertext,
            ]
        ),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(provided_mac, expected_mac):
        raise RuntimeError("Bundle passphrase is incorrect, or the encrypted bundle was modified.")
    return stream_xor(ciphertext, enc_key, nonce)


def create_bundle_archive(ovpn_path: Path, auth_path: Path) -> bytes:
    metadata = {
        "bundle_name": settings().get("bundle_name", "destiny"),
        "created_at": utc_now(),
        "source_ovpn_name": ovpn_path.name,
        "source_auth_name": auth_path.name,
    }
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        with tarfile.open(temp_path, "w:gz") as archive:
            archive.add(ovpn_path, arcname="destiny.ovpn")
            archive.add(auth_path, arcname="auth.txt")
            metadata_bytes = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8")
            with tempfile.NamedTemporaryFile(delete=False) as metadata_handle:
                metadata_path = Path(metadata_handle.name)
            try:
                metadata_path.write_bytes(metadata_bytes)
                archive.add(metadata_path, arcname="bundle-metadata.json")
            finally:
                metadata_path.unlink(missing_ok=True)
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def extract_bundle(passphrase: str) -> dict:
    bundle_path = resolve_asset_path("vpn-bundle.enc.json")
    payload = read_json(bundle_path)
    plaintext = decrypt_bundle_bytes(payload, passphrase)
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        archive_path = temp_dir / "bundle.tar.gz"
        archive_path.write_bytes(plaintext)
        with tarfile.open(archive_path, "r:gz") as archive:
            safe_extract_tar(archive, temp_dir)
        ovpn_path = temp_dir / "destiny.ovpn"
        auth_path = temp_dir / "auth.txt"
        metadata_path = temp_dir / "bundle-metadata.json"
        if not ovpn_path.exists() or not auth_path.exists():
            raise RuntimeError("Encrypted bundle is missing expected files.")
        return {
            "ovpn_text": ovpn_path.read_text(encoding="utf-8"),
            "auth_text": auth_path.read_text(encoding="utf-8"),
            "metadata": read_json(metadata_path) if metadata_path.exists() else {},
        }


def safe_extract_tar(archive: tarfile.TarFile, target_dir: Path) -> None:
    for member in archive.getmembers():
        member_path = (target_dir / member.name).resolve()
        member_path.relative_to(target_dir.resolve())
    archive.extractall(target_dir)


def rewrite_auth_user_pass(ovpn_text: str, auth_path: Path) -> str:
    auth_path_text = auth_path.as_posix()
    lines = ovpn_text.splitlines()
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.strip().startswith("auth-user-pass"):
            updated.append(f"auth-user-pass {auth_path_text}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"auth-user-pass {auth_path_text}")

    # Force UDP protocol to avoid TCP-over-TCP performance degradation on
    # international links (latency amplification + double retransmission).
    # 1) Replace any existing proto line with proto udp (or add if missing).
    # 2) Remove remote entries that explicitly specify tcp — OpenVPN tries
    #    remotes in order, so a TCP remote listed before UDP remotes will
    #    win even when proto udp is set globally.
    filtered: list[str] = []
    proto_seen = False
    for line in updated:
        stripped = line.strip()
        if stripped.startswith("proto "):
            if not proto_seen:
                filtered.append("proto udp")
                proto_seen = True
            # skip original proto line (replace with udp)
        elif stripped.startswith("remote ") and " tcp" in stripped:
            # skip TCP remote entries to prevent TCP-over-TCP
            continue
        else:
            filtered.append(line)
    updated = filtered
    if not proto_seen:
        for i, line in enumerate(updated):
            if line.strip().startswith("nobind"):
                updated.insert(i + 1, "proto udp")
                break

    win_settings = settings().get("windows", {})
    if win_settings.get("route_nopull", False):
        if not any(l.strip().startswith("route-nopull") for l in updated):
            updated.append("route-nopull")
        if not any("pull-filter ignore" in l and "redirect-gateway" in l for l in updated):
            updated.append("pull-filter ignore \"redirect-gateway\"")
        # Filter dhcp-option to prevent server-pushed DNS (e.g. 127.0.0.1) from
        # overriding our Set-DnsClientServerAddress. Without this, OpenVPN's
        # interactive service applies the pushed DNS, making dns.getServers()
        # return ['127.0.0.1'] which breaks Node.js undici fetch() (uses
        # dns.resolve* which queries getServers() directly, bypassing hosts).
        if not any("pull-filter ignore" in l and "dhcp-option" in l for l in updated):
            updated.append("pull-filter ignore \"dhcp-option\"")
        # Filter ping-restart so OpenVPN doesn't internally restart (which
        # bypasses our DNS fix — the restart gets a new tunnel IP but routes
        # and hosts file still point to the old one). Instead we use ping-exit
        # (below) so OpenVPN EXITS, and the watcher does a full reconnect.
        if not any("pull-filter ignore" in l and "ping-restart" in l for l in updated):
            updated.append("pull-filter ignore \"ping-restart\"")
        # Filter register-dns to prevent OpenVPN interactive service from
        # re-registering DNS settings on reconnect.
        if not any("pull-filter ignore" in l and "register-dns" in l for l in updated):
            updated.append("pull-filter ignore \"register-dns\"")
    # Use ping-exit instead of the server's ping-restart: when the connection
    # drops, OpenVPN exits (instead of internally restarting). The watcher
    # detects the dead process and does a full reconnect with DNS fix.
    if win_settings.get("route_nopull", False):
        if not any(l.strip().startswith("ping-exit") for l in updated):
            updated.append("ping-exit 30")
    if win_settings.get("disable_ipv6", False):
        if not any("pull-filter ignore" in l and "route-ipv6" in l for l in updated):
            updated.append("pull-filter ignore \"route-ipv6\"")
        if not any("pull-filter ignore" in l and "ifconfig-ipv6" in l for l in updated):
            updated.append("pull-filter ignore \"ifconfig-ipv6\"")

    return "\n".join(updated) + "\n"


def prompt_bundle_passphrase(args: argparse.Namespace, *, required: bool) -> str | None:
    if getattr(args, "bundle_passphrase", None):
        return args.bundle_passphrase
    env_name = getattr(args, "bundle_passphrase_env", None)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    env_value = os.environ.get("CLI_VPN_BUNDLE_PASSPHRASE")
    if env_value:
        return env_value
    if not required and config_installed():
        return None
    if not sys.stdin.isatty():
        raise RuntimeError("A bundle passphrase is required, but no interactive terminal is available.")
    return getpass.getpass("Bundle passphrase: ")


def install_bundle(passphrase: str) -> None:
    try:
        bundle = extract_bundle(passphrase)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Encrypted bundle is missing from this skill checkout. Rebuild it with package_bundle.py first."
        ) from exc
    ensure_install_dirs()
    auth_path = managed_auth_path()
    ovpn_path = managed_config_path()
    auth_path.write_text(bundle["auth_text"], encoding="utf-8")
    set_owner_only_permissions(auth_path)
    ovpn_path.write_text(rewrite_auth_user_pass(bundle["ovpn_text"], auth_path), encoding="utf-8")
    set_owner_only_permissions(ovpn_path)
    write_json(local_bundle_manifest_path(), bundle["metadata"])


def detect_macos_utun_interfaces() -> dict[str, list[str]]:
    result = {}
    output = command_output(["/sbin/ifconfig", "-l"])
    for interface in output.split():
        if not interface.startswith("utun"):
            continue
        interface_output = command_output(["/sbin/ifconfig", interface])
        ips = re.findall(r"\sinet\s+([0-9.]+)", interface_output)
        result[interface] = ips
    return result


def choose_tunnel_interface(preferred: str | None = None) -> tuple[str, str] | None:
    configured_prefixes = tuple(settings().get("tunnel_ipv4_prefixes", []))
    interfaces = detect_macos_utun_interfaces() if is_macos() else detect_windows_interfaces()
    if preferred and preferred in interfaces:
        for ip in interfaces[preferred]:
            if not configured_prefixes or ip.startswith(configured_prefixes):
                return preferred, ip
    for interface, ips in sorted(interfaces.items(), reverse=True):
        for ip in ips:
            if not configured_prefixes or ip.startswith(configured_prefixes):
                return interface, ip
    return None


def detect_windows_interfaces() -> dict[str, list[str]]:
    payload = powershell_json(
        """
$prefixes = @(%s)
$items = @()
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
    $adapter = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue
    if ($null -eq $adapter) { return }
    $match = $false
    foreach ($prefix in $prefixes) {
        if ($_.IPAddress.StartsWith($prefix)) { $match = $true; break }
    }
    if (-not $match) { return }
    $desc = $adapter.InterfaceDescription
    if ($desc -notmatch 'OpenVPN|TAP|Wintun|DCO|Data Channel Offload') { return }
    $items += [PSCustomObject]@{
        Name = $_.InterfaceAlias
        IPAddress = $_.IPAddress
        InterfaceIndex = $_.InterfaceIndex
        Description = $adapter.InterfaceDescription
        Status = $adapter.Status
    }
}
$items | ConvertTo-Json -Depth 3
"""
        % ",".join(f"'{prefix}'" for prefix in settings().get("tunnel_ipv4_prefixes", []))
    )
    if payload is None:
        return {}
    if isinstance(payload, dict):
        payload = [payload]
    result: dict[str, list[str]] = {}
    for item in payload:
        result[item["Name"]] = [item["IPAddress"]]
    return result


def current_openvpn_pid() -> int | None:
    pid_file = openvpn_pid_path()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None
        if process_exists(pid):
            return pid
    state = load_state()
    pid = state.get("openvpn_pid")
    if isinstance(pid, int) and process_exists(pid):
        return pid
    return None


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if is_windows():
        # On Windows, os.kill(pid, 0) calls TerminateProcess which either
        # kills the process or raises OSError(Access Denied) for elevated
        # processes. Use tasklist instead for a safe existence check.
        result = run_command(
            ["tasklist", "/fi", f"pid eq {pid}", "/fo", "csv", "/nh"],
            capture_output=True,
        )
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def macos_password_from_keychain() -> str | None:
    result = run_command(
        ["security", "find-generic-password", "-a", getpass.getuser(), "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def validate_macos_password(password: str) -> bool:
    result = run_command(
        ["sudo", "-S", "-k", "-v"],
        input_text=password + "\n",
        capture_output=True,
    )
    return result.returncode == 0


def store_macos_password(password: str) -> None:
    run_command(
        [
            "security",
            "add-generic-password",
            "-a",
            getpass.getuser(),
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
            password,
            "-U",
        ],
        check=True,
    )


def delete_macos_password() -> None:
    run_command(
        ["security", "delete-generic-password", "-a", getpass.getuser(), "-s", KEYCHAIN_SERVICE],
        capture_output=True,
    )


def macos_admin_password(*, allow_prompt: bool = True) -> str:
    cached = macos_password_from_keychain()
    if cached and validate_macos_password(cached):
        return cached
    if not allow_prompt or not sys.stdin.isatty():
        raise RuntimeError(
            "macOS admin password is required. Run `cli-vpn-install install` or `vpn` in an interactive shell first."
        )
    while True:
        password = getpass.getpass("macOS admin password (stored in Keychain for cli-vpn-install): ")
        if validate_macos_password(password):
            store_macos_password(password)
            return password
        print("Password validation failed. Try again.", file=sys.stderr)


def sudo_run(password: str, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["sudo", "-S", *command], input_text=password + "\n", check=check)


def detect_default_network_device() -> str | None:
    result = run_command(["route", "get", "default"])
    if result.returncode != 0:
        return None
    match = re.search(r"interface: (\S+)", result.stdout)
    return match.group(1) if match else None


def macos_primary_service() -> str | None:
    device = detect_default_network_device()
    if not device:
        return None
    output = command_output(["networksetup", "-listnetworkserviceorder"])
    pattern = re.compile(r"\((\d+)\) (.+?)\n\(Hardware Port: .+?, Device: (.+?)\)", re.MULTILINE)
    for _, service, current_device in pattern.findall(output):
        if current_device == device:
            return service
    return None


def macos_dns_servers(service: str) -> list[str]:
    result = run_command(["networksetup", "-getdnsservers", service], capture_output=True)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines or "There aren't any DNS Servers set" in result.stdout:
        return []
    return lines


def macos_ipv6_enabled(service: str) -> bool:
    result = run_command(["networksetup", "-getv6networkserviceenabled", service], capture_output=True)
    return result.returncode == 0 and result.stdout.strip().lower() == "enabled"


def apply_macos_network_overrides(password: str, state: dict) -> None:
    mac_settings = settings().get("macos", {})
    service = macos_primary_service()
    if not service:
        return
    state["pre_connect"]["network_service"] = service
    state["pre_connect"]["dns_servers"] = macos_dns_servers(service)
    state["pre_connect"]["ipv6_enabled"] = macos_ipv6_enabled(service)
    if mac_settings.get("disable_ipv6"):
        sudo_run(password, ["networksetup", "-setv6off", service], check=False)
    dns_servers = mac_settings.get("dns_servers", [])
    if dns_servers:
        sudo_run(password, ["networksetup", "-setdnsservers", service, *dns_servers], check=False)


def restore_macos_network_overrides(password: str, state: dict) -> None:
    mac_settings = settings().get("macos", {})
    pre_connect = state.get("pre_connect", {})
    service = pre_connect.get("network_service")
    if not service:
        # pre_connect state was never saved (e.g. watcher restarted OpenVPN
        # without going through the full connect flow). Fall back to the
        # primary service so we can still restore DNS and IPv6.
        service = macos_primary_service()
        if not service:
            return
    dns_servers = pre_connect.get("dns_servers", [])
    if dns_servers:
        sudo_run(password, ["networksetup", "-setdnsservers", service, *dns_servers], check=False)
    else:
        sudo_run(password, ["networksetup", "-setdnsservers", service, "empty"], check=False)
    # Restore IPv6: if we don't know the pre-connect state (empty pre_connect),
    # keep IPv6 off — the user's settings say disable_ipv6: true, so err on the
    # side of keeping it off rather than accidentally re-enabling it.
    if "ipv6_enabled" in pre_connect:
        if pre_connect["ipv6_enabled"]:
            sudo_run(password, ["networksetup", "-setv6automatic", service], check=False)
        else:
            sudo_run(password, ["networksetup", "-setv6off", service], check=False)
    elif mac_settings.get("disable_ipv6"):
        sudo_run(password, ["networksetup", "-setv6off", service], check=False)


def macos_route_command(route: dict, action: str, interface: str) -> list[str]:
    prefix = route["prefix"]
    if route["kind"] == "host":
        return ["/sbin/route", "-n", action, "-host", prefix.split("/", 1)[0], "-interface", interface]
    return ["/sbin/route", "-n", action, "-net", prefix, "-interface", interface]


def apply_routes_macos(password: str, interface: str) -> list[dict]:
    applied: list[dict] = []
    for route in whitelist_routes():
        result = sudo_run(password, macos_route_command(route, "add", interface), check=False)
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 or "File exists" in combined:
            applied.append(route)
    return applied


def remove_routes_macos(password: str, interface: str, routes: list[dict]) -> None:
    for route in routes:
        sudo_run(password, macos_route_command(route, "delete", interface), check=False)


def start_openvpn_macos(password: str) -> None:
    openvpn_binary = ensure_openvpn_binary()
    sudo_run(password, ["pkill", "openvpn"], check=False)
    time.sleep(1)
    sudo_run(
        password,
        [
            openvpn_binary,
            "--daemon",
            "--config",
            str(managed_config_path()),
            "--log-append",
            str(openvpn_log_path()),
            "--writepid",
            str(openvpn_pid_path()),
        ],
        check=True,
    )


def wait_for_tunnel(timeout_seconds: int, preferred_interface: str | None = None) -> tuple[str, str]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        choice = choose_tunnel_interface(preferred_interface)
        if choice:
            return choice
        time.sleep(1)
    raise RuntimeError("Timed out waiting for the VPN tunnel to become ready.")


def start_watcher_process() -> int | None:
    state = load_state()
    pid = state.get("watcher_pid")
    if isinstance(pid, int) and process_exists(pid):
        return pid
    command = [*which_python(), str(runtime_root() / "cli_vpn_install.py"), "watch-loop"]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def stop_watcher_process(pid: int | None) -> None:
    if not pid or not process_exists(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return


def connect_macos(*, quiet: bool = False, start_watcher: bool = True) -> None:
    if not config_installed():
        raise RuntimeError("VPN config is not installed. Run `cli-vpn-install install` first.")
    password = macos_admin_password()
    state = load_state()
    existing = choose_tunnel_interface(state.get("tunnel_interface"))
    if current_openvpn_pid() and existing:
        state["connected"] = True
        state["tunnel_interface"] = existing[0]
        state["tunnel_ip"] = existing[1]
        state["applied_routes"] = apply_routes_macos(password, existing[0])
        if start_watcher:
            state["watcher_pid"] = start_watcher_process()
        save_state(state)
        if not quiet:
            print(f"VPN already connected on {existing[0]} ({existing[1]}). Routes refreshed.")
        return

    apply_macos_network_overrides(password, state)
    previous = detect_macos_utun_interfaces()
    start_openvpn_macos(password)
    interface, ip_address = wait_for_tunnel(settings().get("connect_timeout_seconds", 20))
    new_state = load_state()
    new_state["connected"] = True
    new_state["openvpn_pid"] = current_openvpn_pid()
    new_state["tunnel_interface"] = interface
    new_state["tunnel_ip"] = ip_address
    new_state["applied_routes"] = apply_routes_macos(password, interface)
    new_state["previous_utun_snapshot"] = previous
    if start_watcher:
        new_state["watcher_pid"] = start_watcher_process()
    save_state(new_state)
    if not quiet:
        print(f"VPN connected on {interface} ({ip_address}).")


def disconnect_macos(*, quiet: bool = False) -> None:
    state = load_state()
    password = macos_admin_password()
    stop_watcher_process(state.get("watcher_pid"))
    pid = current_openvpn_pid()
    if pid:
        sudo_run(password, ["kill", str(pid)], check=False)
    else:
        sudo_run(password, ["pkill", "openvpn"], check=False)
    interface = state.get("tunnel_interface")
    if interface:
        remove_routes_macos(password, interface, list(state.get("applied_routes", [])))
    restore_macos_network_overrides(password, state)
    openvpn_pid_path().unlink(missing_ok=True)
    state["connected"] = False
    state["openvpn_pid"] = None
    state["watcher_pid"] = None
    state["tunnel_interface"] = None
    state["tunnel_ip"] = None
    state["applied_routes"] = []
    state["pre_connect"] = {}
    save_state(state)
    if not quiet:
        print("VPN disconnected.")


def powershell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=check,
    )


def powershell_json(command: str):
    result = powershell(command, check=False)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return json.loads(output)


def windows_task_name(suffix: str) -> str:
    return f"CodexCliVpnInstall{suffix}"


def is_windows_admin() -> bool:
    import ctypes

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_windows_tasks_registered() -> None:
    missing = []
    for suffix in ("Connect", "Disconnect", "Watch"):
        result = run_command(["schtasks", "/Query", "/TN", windows_task_name(suffix)], capture_output=True)
        if result.returncode != 0:
            missing.append(suffix)
    if not missing:
        return
    register_windows_tasks()


def register_windows_tasks() -> None:
    if not is_windows():
        return
    write_windows_support_scripts()
    if is_windows_admin():
        powershell(
            f"& '{(runtime_root() / WINDOWS_REGISTER_SCRIPT)}'",
            check=True,
        )
        return
    command = (
        "Start-Process PowerShell "
        "-Verb RunAs "
        f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{runtime_root() / WINDOWS_REGISTER_SCRIPT}\"' "
        "-Wait"
    )
    result = powershell(command, check=False)
    if result.returncode != 0:
        raise RuntimeError("Failed to register elevated Windows helper tasks.")


def unregister_windows_tasks() -> None:
    if not is_windows():
        return
    if is_windows_admin():
        powershell(f"& '{(runtime_root() / WINDOWS_UNREGISTER_SCRIPT)}'", check=False)
        return
    command = (
        "Start-Process PowerShell "
        "-Verb RunAs "
        f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{runtime_root() / WINDOWS_UNREGISTER_SCRIPT}\"' "
        "-Wait"
    )
    powershell(command, check=False)


def windows_find_tunnel() -> dict | None:
    payload = powershell_json(
        """
$prefixes = @(%s)
$items = @()
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
    $adapter = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue
    if ($null -eq $adapter) { return }
    $matchesPrefix = $false
    foreach ($prefix in $prefixes) {
        if ($_.IPAddress.StartsWith($prefix)) { $matchesPrefix = $true; break }
    }
    if (-not $matchesPrefix) { return }
    if ($adapter.Status -ne 'Up') { return }
    $desc = $adapter.InterfaceDescription
    if ($desc -notmatch 'OpenVPN|TAP|Wintun|DCO|Data Channel Offload') { return }
    $items += [PSCustomObject]@{
        InterfaceAlias = $_.InterfaceAlias
        InterfaceIndex = $_.InterfaceIndex
        IPAddress = $_.IPAddress
        InterfaceDescription = $adapter.InterfaceDescription
    }
}
$items | Select-Object -First 1 | ConvertTo-Json -Depth 3
"""
        % ",".join(f"'{prefix}'" for prefix in settings().get("tunnel_ipv4_prefixes", []))
    )
    return payload if isinstance(payload, dict) else None


def windows_kill_openvpn() -> None:
    """Kill any existing OpenVPN process to release the DCO adapter."""
    run_command(["taskkill", "/IM", "openvpn.exe", "/F"], capture_output=True, check=False)
    # Brief pause to let the OS release the DCO adapter
    time.sleep(1)


def start_openvpn_windows() -> int:
    openvpn_binary = ensure_openvpn_binary()
    creation_flags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creation_flags |= subprocess.DETACHED_PROCESS
    cmd = [
        openvpn_binary,
        "--config",
        str(managed_config_path()),
        "--log-append",
        str(openvpn_log_path()),
        "--writepid",
        str(openvpn_pid_path()),
    ]
    win_settings = settings().get("windows", {})
    if win_settings.get("route_nopull", False):
        cmd.append("--route-nopull")
    process = subprocess.Popen(
        cmd,
        creationflags=creation_flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
    )
    return process.pid


def apply_routes_windows(interface_index: int) -> list[dict]:
    applied: list[dict] = []
    for route in whitelist_routes():
        prefix = route["prefix"]
        powershell(
            """
$existing = Get-NetRoute -DestinationPrefix '%s' -InterfaceIndex %d -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
}
New-NetRoute -DestinationPrefix '%s' -InterfaceIndex %d -NextHop '0.0.0.0' -PolicyStore ActiveStore -RouteMetric 1 -ErrorAction Stop | Out-Null
"""
            % (prefix, interface_index, prefix, interface_index),
            check=False,
        )
        applied.append(route)
    return applied


def remove_routes_windows(interface_index: int, routes: list[dict]) -> None:
    for route in routes:
        powershell(
            """
$existing = Get-NetRoute -DestinationPrefix '%s' -InterfaceIndex %d -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
}
"""
            % (route["prefix"], interface_index),
            check=False,
        )


def wait_for_windows_tunnel(timeout_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = windows_find_tunnel()
        if payload:
            return payload
        time.sleep(1)
    raise RuntimeError("Timed out waiting for the Windows VPN tunnel to become ready.")


GOOGLE_IPV6_RANGES = [
    "2404:6800::/32",
    "2600:1900::/28",
    "2607:f8b0::/32",
    "2800:3f0::/48",
    "2a00:1450::/40",
]

FIREWALL_RULE_PREFIX = "CliVpnBlockGoogleIPv6"


def disable_windows_tunnel_ipv6(interface_alias: str) -> None:
    powershell(
        f"Disable-NetAdapterBinding -Name '{interface_alias}' -ComponentID ms_tcpip6 -ErrorAction SilentlyContinue",
        check=False,
    )


def enable_windows_tunnel_ipv6(interface_alias: str) -> None:
    powershell(
        f"Enable-NetAdapterBinding -Name '{interface_alias}' -ComponentID ms_tcpip6 -ErrorAction SilentlyContinue",
        check=False,
    )


def add_google_ipv6_firewall_rules() -> None:
    for cidr in GOOGLE_IPV6_RANGES:
        rule_name = f"{FIREWALL_RULE_PREFIX}_{cidr.replace(':', '_').replace('/', '_')}"
        powershell(
            f"""
$existing = Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue
if ($existing) {{ Remove-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue }}
New-NetFirewallRule -DisplayName '{rule_name}' -Direction Outbound -Action Block -RemoteAddress '{cidr}' -Profile Any -Enabled True -Group 'CliVpn' | Out-Null
""",
            check=False,
        )


def remove_google_ipv6_firewall_rules() -> None:
    powershell(
        f"Get-NetFirewallRule -DisplayName '{FIREWALL_RULE_PREFIX}*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue",
        check=False,
    )


def windows_watch_task_running() -> bool:
    # Use PowerShell Get-ScheduledTask instead of schtasks, because schtasks
    # /FO LIST /V outputs localized text (e.g. "状态: 正在运行" on Chinese
    # Windows) making the English string check unreliable.
    result = powershell(
        f"(Get-ScheduledTask -TaskName '{windows_task_name('Watch')}' -ErrorAction SilentlyContinue).State",
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "running"


# --- DNS anti-poisoning via hosts file ---

HOSTS_MARKER_BEGIN = "# BEGIN CLI-VPN DNS FIX"
HOSTS_MARKER_END = "# END CLI-VPN DNS FIX"
HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")

DNS_FIX_DOMAINS = [
    "www.google.com",
    "google.com",
    "accounts.google.com",
    "accounts.google.com.sg",
    "mail.google.com",
    "drive.google.com",
    "docs.google.com",
    "gemini.google.com",
    "www.youtube.com",
    "youtube.com",
    "github.com",
    "api.github.com",
    "raw.githubusercontent.com",
    "gist.github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "api.telegram.org",
    "api.openai.com",
    "chat.openai.com",
    "platform.openai.com",
    "create-gemini-temp-images.hkseek-muigoelqy.workers.dev",
]


def resolve_via_vpn_dns(domain: str) -> list[str]:
    try:
        result = run_command(
            ["nslookup", domain, "8.8.8.8"],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    ips: list[str] = []
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", stripped) and stripped not in ("8.8.8.8", "8.8.4.4"):
            ips.append(stripped)
    return ips


def refresh_dns_hosts_windows() -> None:
    entries: list[str] = []
    for domain in DNS_FIX_DOMAINS:
        for ip in resolve_via_vpn_dns(domain):
            entries.append(f"{ip} {domain}")
    if not entries:
        return
    old_content = HOSTS_PATH.read_text(encoding="utf-8", errors="ignore") if HOSTS_PATH.exists() else ""
    if HOSTS_MARKER_BEGIN in old_content:
        pattern = re.compile(re.escape(HOSTS_MARKER_BEGIN) + r".*?" + re.escape(HOSTS_MARKER_END) + r"\n?", re.DOTALL)
        old_content = pattern.sub("", old_content)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    new_block = f"\n{HOSTS_MARKER_BEGIN} ({timestamp})\n"
    new_block += "# Auto-generated by cli-vpn-install to bypass DNS poisoning\n"
    for entry in sorted(set(entries)):
        new_block += f"{entry}\n"
    new_block += f"{HOSTS_MARKER_END}\n"
    HOSTS_PATH.write_text(old_content.rstrip() + "\n" + new_block, encoding="ascii", errors="ignore")
    run_command(["ipconfig", "/flushdns"], capture_output=True, check=False)


def clean_dns_hosts_windows() -> None:
    if not HOSTS_PATH.exists():
        return
    content = HOSTS_PATH.read_text(encoding="utf-8", errors="ignore")
    if HOSTS_MARKER_BEGIN not in content:
        return
    pattern = re.compile(re.escape(HOSTS_MARKER_BEGIN) + r".*?" + re.escape(HOSTS_MARKER_END) + r"\n?", re.DOTALL)
    content = pattern.sub("", content).rstrip() + "\n"
    HOSTS_PATH.write_text(content, encoding="ascii", errors="ignore")
    run_command(["ipconfig", "/flushdns"], capture_output=True, check=False)


def set_windows_primary_dns() -> None:
    result = run_command(
        ["powershell", "-Command",
         "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1; "
         "$idx = $r.InterfaceIndex; "
         "$dns = Get-DnsClientServerAddress -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue; "
         "if ($dns) { $dns.ServerAddresses -join ',' } else { '' }"],
        capture_output=True,
    )
    old_dns = result.stdout.strip() if result.stdout else ""
    state = load_state()
    state["original_dns"] = old_dns
    save_state(state)
    run_command(
        ["powershell", "-Command",
         "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1; "
         "$idx = $r.InterfaceIndex; "
         "Set-DnsClientServerAddress -InterfaceIndex $idx -ServerAddresses @('8.8.8.8','1.1.1.1')"],
        capture_output=True, check=False,
    )
    # Clear IPv6 DNS (e.g. ::1) on ALL interfaces to prevent GFW DNS poisoning
    # via getaddrinfo fallback. ::1 has no resolver listening, so the system
    # falls back to IPv4 8.8.8.8 whose UDP-53 packets get poisoned by the GFW.
    # NOTE: Set-DnsClientServerAddress in PS 5.1 lacks -AddressFamily, so use
    # netsh interface ipv6 delete dns <idx> all to clear IPv6 DNS only.
    # ALSO clear ::1 directly from the registry (Tcpip6 Parameters Interfaces),
    # because netsh alone does not remove the NameServer registry value —
    # GetNetworkParams still reads ::1 from registry, causing dns.getServers()
    # to return ['127.0.0.1'] which breaks dns.resolve*() in Node.js.
    result = run_command(
        ["powershell", "-Command",
         "Get-DnsClientServerAddress -AddressFamily IPv6 -ErrorAction SilentlyContinue | "
         "Where-Object { $_.ServerAddresses -contains '::1' } | "
         "Select-Object -ExpandProperty InterfaceIndex"],
        capture_output=True, check=False,
    )
    for line in (result.stdout or "").splitlines():
        idx = line.strip()
        if idx.isdigit():
            run_command(
                ["netsh", "interface", "ipv6", "delete", "dns", idx, "all"],
                capture_output=True, check=False,
            )
    # Directly clear ::1 from IPv6 registry entries (netsh is not thorough enough)
    run_command(
        ["powershell", "-Command",
         "Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters\\Interfaces' | "
         "ForEach-Object { "
         "  $ns = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).NameServer; "
         "  if ($ns -and $ns -match '::1') { "
         "    Set-ItemProperty -Path $_.PSPath -Name 'NameServer' -Value '' -Type String -Force; "
         "  } "
         "}"],
        capture_output=True, check=False,
    )
    run_command(["ipconfig", "/flushdns"], capture_output=True, check=False)


def restore_windows_primary_dns() -> None:
    state = load_state()
    old_dns_str = state.get("original_dns", "")
    if not old_dns_str:
        return
    old_dns = [s.strip() for s in old_dns_str.split(",") if s.strip()]
    result = run_command(
        ["powershell", "-Command",
         "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1; "
         "$idx = $r.InterfaceIndex; "
         f"Set-DnsClientServerAddress -InterfaceIndex $idx -ServerAddresses @({','.join([repr(d) for d in old_dns])})"],
        capture_output=True, check=False,
    )
    state["original_dns"] = None
    save_state(state)
    run_command(["ipconfig", "/flushdns"], capture_output=True, check=False)


def ensure_windows_watch_task() -> None:
    if windows_watch_task_running():
        return
    run_command(["schtasks", "/Run", "/TN", windows_task_name("Watch")], capture_output=True, check=False)


def windows_connect_elevated(*, quiet: bool = False, start_watcher: bool = True) -> None:
    if not config_installed():
        raise RuntimeError("VPN config is not installed. Run `cli-vpn-install install` first.")
    state = load_state()
    win_settings = settings().get("windows", {})
    existing = windows_find_tunnel()
    if current_openvpn_pid() and existing:
        state["connected"] = True
        state["tunnel_interface"] = existing["InterfaceAlias"]
        state["tunnel_ip"] = existing["IPAddress"]
        state["tunnel_interface_index"] = existing["InterfaceIndex"]
        state["applied_routes"] = apply_routes_windows(existing["InterfaceIndex"])
        if win_settings.get("disable_ipv6", False):
            disable_windows_tunnel_ipv6(existing["InterfaceAlias"])
        if win_settings.get("block_google_ipv6", False):
            add_google_ipv6_firewall_rules()
        if win_settings.get("dns_fix", True):
            set_windows_primary_dns()
            refresh_dns_hosts_windows()
        save_state(state)
        if start_watcher:
            ensure_windows_watch_task()
        if not quiet:
            print(f"VPN already connected on {existing['InterfaceAlias']} ({existing['IPAddress']}). Routes refreshed.")
        return

    # Kill any stale OpenVPN process before starting a fresh one.
    # Without this, the old process may still hold the DCO adapter,
    # causing the new process to fail or the tunnel to drop repeatedly.
    windows_kill_openvpn()
    state["openvpn_pid"] = start_openvpn_windows()
    tunnel = wait_for_windows_tunnel(settings().get("connect_timeout_seconds", 20))
    state["connected"] = True
    state["openvpn_pid"] = current_openvpn_pid() or state["openvpn_pid"]
    state["tunnel_interface"] = tunnel["InterfaceAlias"]
    state["tunnel_ip"] = tunnel["IPAddress"]
    state["tunnel_interface_index"] = tunnel["InterfaceIndex"]
    state["applied_routes"] = apply_routes_windows(tunnel["InterfaceIndex"])
    if win_settings.get("disable_ipv6", False):
        disable_windows_tunnel_ipv6(tunnel["InterfaceAlias"])
    if win_settings.get("block_google_ipv6", False):
        add_google_ipv6_firewall_rules()
    if win_settings.get("dns_fix", True):
        set_windows_primary_dns()
        refresh_dns_hosts_windows()
    save_state(state)
    if start_watcher:
        ensure_windows_watch_task()
    if not quiet:
        print(f"VPN connected on {tunnel['InterfaceAlias']} ({tunnel['IPAddress']}).")


def windows_disconnect_elevated(*, quiet: bool = False) -> None:
    state = load_state()
    win_settings = settings().get("windows", {})
    run_command(["schtasks", "/End", "/TN", windows_task_name("Watch")], capture_output=True, check=False)
    pid = current_openvpn_pid()
    if pid:
        run_command(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False)
    interface_alias = state.get("tunnel_interface")
    if interface_alias and win_settings.get("disable_ipv6", False):
        enable_windows_tunnel_ipv6(interface_alias)
    if win_settings.get("block_google_ipv6", False):
        remove_google_ipv6_firewall_rules()
    if win_settings.get("dns_fix", True):
        clean_dns_hosts_windows()
        restore_windows_primary_dns()
    interface_index = state.get("tunnel_interface_index")
    if isinstance(interface_index, int):
        remove_routes_windows(interface_index, list(state.get("applied_routes", [])))
    openvpn_pid_path().unlink(missing_ok=True)
    state["connected"] = False
    state["openvpn_pid"] = None
    state["watcher_pid"] = None
    state["tunnel_interface"] = None
    state["tunnel_interface_index"] = None
    state["tunnel_ip"] = None
    state["applied_routes"] = []
    save_state(state)
    if not quiet:
        print("VPN disconnected.")


def trigger_windows_task(action: str) -> None:
    ensure_windows_tasks_registered()
    suffix = "Connect" if action == "connect" else "Disconnect"
    result = run_command(["schtasks", "/Run", "/TN", windows_task_name(suffix)], capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Failed to start Windows helper task: {stderr}")


def wait_for_windows_connection_state(expected_connected: bool) -> None:
    deadline = time.time() + settings().get("connect_timeout_seconds", 20)
    while time.time() < deadline:
        connected = windows_find_tunnel() is not None
        if connected == expected_connected:
            return
        time.sleep(1)
    state_text = "connected" if expected_connected else "disconnected"
    raise RuntimeError(f"Timed out waiting for the VPN to become {state_text}.")


def connect_command() -> None:
    if is_macos():
        connect_macos()
        return
    if is_windows():
        trigger_windows_task("connect")
        wait_for_windows_connection_state(True)
        print("VPN connect task completed.")
        return
    raise RuntimeError("cli-vpn-install currently supports macOS and Windows only.")


def disconnect_command() -> None:
    if is_macos():
        disconnect_macos()
        return
    if is_windows():
        trigger_windows_task("disconnect")
        wait_for_windows_connection_state(False)
        print("VPN disconnect task completed.")
        return
    raise RuntimeError("cli-vpn-install currently supports macOS and Windows only.")


def status_payload() -> dict:
    state = load_state()
    payload = {
        "platform": platform.system(),
        "codex_home": str(codex_home()),
        "install_root": str(install_root()),
        "runtime_installed": (runtime_root() / "cli_vpn_install.py").exists(),
        "bundle_available": bundle_available(),
        "config_installed": config_installed(),
        "openvpn_binary": find_openvpn_binary(),
        "connected": False,
        "tunnel_interface": state.get("tunnel_interface"),
        "tunnel_ip": state.get("tunnel_ip"),
        "watcher_running": False,
        "route_count": len(state.get("applied_routes", [])),
        "keychain_password_present": False,
        "windows_tasks_registered": None,
    }
    if is_macos():
        tunnel = choose_tunnel_interface(state.get("tunnel_interface"))
        payload["connected"] = bool(current_openvpn_pid() and tunnel)
        payload["tunnel_interface"] = tunnel[0] if payload["connected"] and tunnel else None
        payload["tunnel_ip"] = tunnel[1] if payload["connected"] and tunnel else None
        payload["watcher_running"] = bool(state.get("watcher_pid") and process_exists(state["watcher_pid"]))
        payload["keychain_password_present"] = macos_password_from_keychain() is not None
    elif is_windows():
        tunnel = windows_find_tunnel()
        payload["connected"] = tunnel is not None
        if payload["connected"] and tunnel:
            payload["tunnel_interface"] = tunnel["InterfaceAlias"]
            payload["tunnel_ip"] = tunnel["IPAddress"]
        else:
            payload["tunnel_interface"] = None
            payload["tunnel_ip"] = None
        payload["watcher_running"] = windows_watch_task_running()
        registered = True
        for suffix in ("Connect", "Disconnect", "Watch"):
            result = run_command(["schtasks", "/Query", "/TN", windows_task_name(suffix)], capture_output=True)
            if result.returncode != 0:
                registered = False
                break
        payload["windows_tasks_registered"] = registered
    return payload


def install_command(args: argparse.Namespace) -> None:
    ensure_openvpn_binary()
    copied = install_runtime_assets()
    install_wrappers()
    if is_windows():
        update_windows_path()
    else:
        update_unix_path()

    if args.bundle_passphrase or args.bundle_passphrase_env or not config_installed():
        passphrase = prompt_bundle_passphrase(args, required=not config_installed())
        if passphrase:
            install_bundle(passphrase)

    if is_windows():
        try:
            register_windows_tasks()
        except Exception as exc:
            print(f"Windows helper task registration skipped: {exc}", file=sys.stderr)

    state = load_state()
    state["installed_at"] = state.get("installed_at") or utc_now()
    save_state(state)
    print(f"Installed runtime files: {len(copied)}")
    print(f"Command wrappers are available under {wrapper_root()}")
    if not config_installed():
        print("VPN config is not installed yet. Re-run with a valid bundle passphrase.", file=sys.stderr)


def uninstall_command(_args: argparse.Namespace) -> None:
    try:
        if is_macos():
            disconnect_macos(quiet=True)
        elif is_windows():
            windows_disconnect_elevated(quiet=True)
    except Exception:
        pass

    if is_macos():
        delete_macos_password()
        remove_unix_path_block()
    elif is_windows():
        unregister_windows_tasks()
        remove_windows_path()

    for wrapper_name in ("cli-vpn-install", "vpn", "voff"):
        path = wrapper_root() / (f"{wrapper_name}.cmd" if is_windows() else wrapper_name)
        path.unlink(missing_ok=True)

    shutil.rmtree(install_root(), ignore_errors=True)
    print(f"Removed {install_root()}")


def status_command(args: argparse.Namespace) -> None:
    payload = status_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"Platform: {payload['platform']}")
    print(f"Runtime installed: {'yes' if payload['runtime_installed'] else 'no'}")
    print(f"Encrypted bundle available: {'yes' if payload['bundle_available'] else 'no'}")
    print(f"Config installed: {'yes' if payload['config_installed'] else 'no'}")
    print(f"OpenVPN binary: {payload['openvpn_binary'] or 'missing'}")
    print(f"Connected: {'yes' if payload['connected'] else 'no'}")
    if payload["tunnel_interface"]:
        print(f"Tunnel: {payload['tunnel_interface']} ({payload['tunnel_ip']})")
    print(f"Watcher running: {'yes' if payload['watcher_running'] else 'no'}")
    print(f"Managed route count: {payload['route_count']}")
    if is_macos():
        print(f"Keychain admin password stored: {'yes' if payload['keychain_password_present'] else 'no'}")
    if is_windows():
        print(f"Windows helper tasks registered: {'yes' if payload['windows_tasks_registered'] else 'no'}")


WATCH_LOOP_RUNNING = True


def stop_watch_loop(_signum, _frame) -> None:
    global WATCH_LOOP_RUNNING
    WATCH_LOOP_RUNNING = False


def watch_loop_command() -> None:
    signal.signal(signal.SIGTERM, stop_watch_loop)
    signal.signal(signal.SIGINT, stop_watch_loop)
    interval = settings().get("watch_interval_seconds", 60)
    log_watch("watcher started")
    while WATCH_LOOP_RUNNING:
        time.sleep(interval)
        try:
            if is_macos():
                tunnel = choose_tunnel_interface(load_state().get("tunnel_interface"))
                if not current_openvpn_pid() or not tunnel:
                    log_watch("tunnel dropped, reconnecting")
                    connect_macos(quiet=True, start_watcher=False)
            elif is_windows():
                tunnel = windows_find_tunnel()
                if not current_openvpn_pid() or not tunnel:
                    # Double-check after a brief pause to avoid false positives
                    # caused by transient PowerShell latency or adapter flicker.
                    time.sleep(3)
                    tunnel = windows_find_tunnel()
                    if not current_openvpn_pid() or not tunnel:
                        log_watch("tunnel dropped, reconnecting")
                        windows_connect_elevated(quiet=True, start_watcher=False)
        except Exception as exc:
            log_watch(f"watcher error: {exc}")
    log_watch("watcher stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--bundle-passphrase")
    install_parser.add_argument("--bundle-passphrase-env")
    install_parser.set_defaults(func=install_command)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=status_command)

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.set_defaults(func=uninstall_command)

    connect_parser = subparsers.add_parser("connect")
    connect_parser.set_defaults(func=lambda _args: connect_command())

    disconnect_parser = subparsers.add_parser("disconnect")
    disconnect_parser.set_defaults(func=lambda _args: disconnect_command())

    watch_parser = subparsers.add_parser("watch-loop")
    watch_parser.set_defaults(func=lambda _args: watch_loop_command())

    elevated_connect_parser = subparsers.add_parser("elevated-connect")
    elevated_connect_parser.set_defaults(func=lambda _args: windows_connect_elevated())

    elevated_disconnect_parser = subparsers.add_parser("elevated-disconnect")
    elevated_disconnect_parser.set_defaults(func=lambda _args: windows_disconnect_elevated())

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("remainder", nargs=argparse.REMAINDER)
    dispatch_parser.set_defaults(func=dispatch_command)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(2)
    return args


def dispatch_command(args: argparse.Namespace) -> None:
    forwarded = list(args.remainder)
    if not forwarded:
        status_command(argparse.Namespace(json=False))
        return
    sys.argv = [sys.argv[0], *forwarded]
    parsed = parse_args()
    parsed.func(parsed)


def main() -> int:
    try:
        args = parse_args()
        result = args.func(args)
        return 0 if result is None else int(result)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
