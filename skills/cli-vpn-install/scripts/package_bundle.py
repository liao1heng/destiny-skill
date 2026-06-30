#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from cli_vpn_install import create_bundle_archive, encrypt_bytes_to_bundle, source_asset_dir, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="package_bundle.py")
    parser.add_argument("--ovpn-path", default=str(Path.home() / ".openvpn" / "destiny.ovpn"))
    parser.add_argument("--auth-path", default=str(Path.home() / ".openvpn" / "auth.txt"))
    parser.add_argument("--output-path", default=str(source_asset_dir() / "vpn-bundle.enc.json"))
    parser.add_argument("--passphrase")
    parser.add_argument("--passphrase-env")
    return parser.parse_args()


def resolve_passphrase(args: argparse.Namespace) -> str:
    if args.passphrase:
        return args.passphrase
    if args.passphrase_env and os.environ.get(args.passphrase_env):
        return os.environ[args.passphrase_env]
    if os.environ.get("CLI_VPN_BUNDLE_PASSPHRASE"):
        return os.environ["CLI_VPN_BUNDLE_PASSPHRASE"]
    if not os.isatty(0):
        raise RuntimeError("A bundle passphrase is required.")
    return getpass.getpass("Bundle passphrase: ")


def main() -> int:
    args = parse_args()
    passphrase = resolve_passphrase(args)
    ovpn_path = Path(args.ovpn_path).expanduser().resolve()
    auth_path = Path(args.auth_path).expanduser().resolve()
    if not ovpn_path.exists():
        raise SystemExit(f"Missing ovpn file: {ovpn_path}")
    if not auth_path.exists():
        raise SystemExit(f"Missing auth file: {auth_path}")
    payload = encrypt_bytes_to_bundle(create_bundle_archive(ovpn_path, auth_path), passphrase)
    output_path = Path(args.output_path).expanduser().resolve()
    write_json(output_path, payload)
    print(f"Wrote encrypted bundle to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
