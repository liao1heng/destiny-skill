#!/usr/bin/env python3
"""Register GitHub projects and clone missing checkouts without altering existing projects."""
import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

CATALOG_REPO = "https://github.com/liao1heng/destiny-skill.git"
CATALOG_PATH = "skills/cli-repo/references/repos.json"
LOCAL_CATALOG = Path(__file__).resolve().parents[1] / "references" / "repos.json"


def workspace_root():
    if sys.platform == "win32":
        return Path("D:/Workspace")
    if sys.platform == "darwin":
        return Path.home() / "Documents" / "workspace"
    raise RuntimeError("cli-repo 支持 macOS 和 Windows")


def normalize_url(value):
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.split(":", 1)[1]
    if value.startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.split("ssh://git@github.com/", 1)[1]
    p = urlparse(value)
    if p.scheme != "https" or p.netloc.lower() != "github.com" or p.query or p.fragment:
        raise ValueError("需要不含凭据的 GitHub HTTPS/SSH 地址")
    parts = p.path.strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", x) or x in (".", "..") for x in parts):
        raise ValueError("GitHub 仓库地址格式错误")
    return "https://github.com/" + "/".join(parts) + ".git"


def validate_catalog(data):
    entries = data["repositories"]
    if not isinstance(entries, list):
        raise ValueError("清单 repositories 必须是列表")
    paths, urls, result = set(), set(), []
    for entry in entries:
        url = normalize_url(entry["url"])
        name = entry["path"]
        p = PurePosixPath(name)
        if not name or p.is_absolute() or any(x.casefold() in ("", ".", "..", ".git") for x in name.split("/")) or "\\" in name or ":" in name or any(ord(c) < 32 for c in name):
            raise ValueError("清单目录必须是安全的工作区相对路径")
        key = name.casefold()
        if key in paths or url.casefold() in urls:
            raise ValueError("清单目录或地址重复")
        paths.add(key); urls.add(url.casefold())
        result.append({"url": url, "path": name})
    return sorted(result, key=lambda x: (len(PurePosixPath(x["path"]).parts), x["path"].casefold()))


def git_environment():
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    token = next((os.environ[k] for k in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_MCP_PAT") if os.environ.get(k)), None)
    if not token and shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0:
            token = r.stdout.strip()
    if token:
        n = int(env.get("GIT_CONFIG_COUNT", "0"))
        env[f"GIT_CONFIG_KEY_{n}"] = "http.https://github.com/.extraheader"
        env[f"GIT_CONFIG_VALUE_{n}"] = "AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode()
        env["GIT_CONFIG_COUNT"] = str(n + 1)
    return env


def git(args, repo=None, check=True):
    cmd = ["git"] + (["-C", str(repo)] if repo else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, env=git_environment())
    if check and r.returncode:
        # Do not echo remote command arguments, credentials, or arbitrary Git output.
        raise RuntimeError("Git 操作失败：" + args[0] + "；检查网络、权限及目录状态")
    return r


def read_remote_catalog():
    # A temporary clone never changes the user's destiny-skill worktree/index.
    with tempfile.TemporaryDirectory(prefix="cli-repo-catalog-") as tmp:
        repo = Path(tmp) / "catalog"
        git(["clone", "--depth", "1", "--branch", "main", CATALOG_REPO, str(repo)])
        return validate_catalog(json.loads((repo / CATALOG_PATH).read_text(encoding="utf-8")))


def checkout_matches(target, url):
    top = git(["rev-parse", "--show-toplevel"], target, check=False)
    if top.returncode or Path(top.stdout.strip()).resolve() != target.resolve():
        return False
    remotes = git(["remote"], target).stdout.splitlines()
    for remote in remotes:
        r = git(["remote", "get-url", remote], target, check=False)
        try:
            if r.returncode == 0 and normalize_url(r.stdout.strip()).casefold() == url.casefold():
                return True
        except ValueError:
            pass
    return False


def ensure_repositories(entries, root, clone=True):
    root = root.expanduser().resolve()
    result = []
    blocked = []
    for entry in validate_catalog({"repositories": entries}):
        target = root / entry["path"]
        if any(PurePosixPath(entry["path"]).is_relative_to(p) for p in blocked):
            result.append({**entry, "status": "conflict"}); continue
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            blocked.append(PurePosixPath(entry["path"]))
            result.append({**entry, "status": "conflict"}); continue
        if target.exists():
            state = "existing" if target.is_dir() and checkout_matches(target, entry["url"]) else "conflict"
            if state == "conflict": blocked.append(PurePosixPath(entry["path"]))
            result.append({**entry, "status": state}); continue
        if not clone:
            result.append({**entry, "status": "missing"}); continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # Clone elsewhere, then rename only a completed checkout into place.
        with tempfile.TemporaryDirectory(prefix=".cli-repo-", dir=target.parent) as tmp:
            stage = Path(tmp) / "checkout"
            try:
                git(["clone", entry["url"], str(stage)])
                if target.exists():
                    raise RuntimeError("目标目录在克隆期间出现")
                stage.rename(target)
                state = "cloned"
            except (RuntimeError, OSError):
                state = "failed"
        if state == "failed": blocked.append(PurePosixPath(entry["path"]))
        result.append({**entry, "status": state})
    return result


def discover_project(project, root, selected_url=None):
    top = Path(git(["rev-parse", "--show-toplevel"], project).stdout.strip()).resolve()
    try:
        relative = top.relative_to(root.expanduser().resolve()).as_posix()
    except ValueError:
        raise ValueError("项目不在固定工作区内；请明确目标目录，不自动移动")
    candidates = set()
    for remote in git(["remote"], top).stdout.splitlines():
        try:
            candidates.add(normalize_url(git(["remote", "get-url", remote], top).stdout.strip()))
        except ValueError:
            pass
    if selected_url:
        selected_url = normalize_url(selected_url)
        if selected_url not in candidates:
            raise ValueError("指定地址不是当前项目远端")
        candidates = {selected_url}
    if len(candidates) != 1:
        raise ValueError("请指定唯一 GitHub 远端：" + ", ".join(sorted(candidates)))
    entry = {"url": candidates.pop(), "path": relative}
    validate_catalog({"repositories": [entry]})
    return entry


def register_project(entry):
    with tempfile.TemporaryDirectory(prefix="cli-repo-register-") as tmp:
        repo = Path(tmp) / "catalog"
        git(["clone", "--depth", "1", "--branch", "main", CATALOG_REPO, str(repo)])
        path = repo / CATALOG_PATH
        entries = validate_catalog(json.loads(path.read_text(encoding="utf-8")))
        if entry in entries:
            return {"status": "already_registered", **entry}
        entries = validate_catalog({"repositories": entries + [entry]})
        body = json.dumps({"repositories": entries}, ensure_ascii=False, indent=2) + "\n"
        path.write_text(body, encoding="utf-8")
        git(["add", CATALOG_PATH], repo)
        git(["commit", "-m", "Register project " + entry["path"]], repo)
        git(["push", "origin", "HEAD:main"], repo)
        LOCAL_CATALOG.write_text(body, encoding="utf-8")
        return {"status": "registered", **entry}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["clone", "add", "status"], default="clone")
    parser.add_argument("--project", default=str(Path.cwd()))
    parser.add_argument("--url")
    args = parser.parse_args()
    root = workspace_root()
    if args.mode == "add":
        result = register_project(discover_project(args.project, root, args.url))
        failed = False
    else:
        result = ensure_repositories(read_remote_catalog(), root, clone=args.mode == "clone")
        failed = any(e["status"] in ("conflict", "failed") for e in result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
