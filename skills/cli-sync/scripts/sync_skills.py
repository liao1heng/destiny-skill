#!/usr/bin/env python3
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlparse


DEFAULT_REMOTE_URL = "https://github.com/liao1heng/destiny-skill.git"
DEFAULT_BRANCH = "main"
DEFAULT_GITHUB_USERNAME = "liao1heng"
DEFAULT_MANAGED_SKILLS = [
    "cli-arc",
    "cli-des",
    "cli-dev",
    "cli-init",
    "cli-pm",
    "cli-sync",
    "cli-test",
    "figma",
]
IGNORE_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
IGNORE_SUFFIXES = {".pyc", ".pyo"}


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def local_skills_path() -> Path:
    return codex_home() / "skills"


def managed_repo_path() -> Path:
    return codex_home() / "repos" / "destiny-skill"


def basic_auth_header(username: str, token: str) -> str:
    raw = f"{username}:{token}".encode("ascii")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"AUTHORIZATION: basic {encoded}"


def normalize_remote_url(url: str | None) -> str | None:
    if not url:
        return None

    value = url.strip()
    if not value:
        return None

    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.split(":", 1)[1]
    elif value.startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.split("ssh://git@github.com/", 1)[1]
    elif value.startswith("https://") or value.startswith("http://"):
        parsed = urlparse(value)
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
        value = f"https://{host}/{path}"

    if value.endswith(".git"):
        value = value[:-4]
    return value.rstrip("/")


def run_git(
    repo_path: Path | None,
    args: list[str],
    *,
    username: str | None,
    token: str | None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["git"]
    if repo_path is not None:
        command.extend(["-C", str(repo_path)])
    if username and token:
        command.extend(["-c", f"http.extraheader={basic_auth_header(username, token)}"])
    command.extend(args)
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git is required for cli-sync but was not found in PATH.")


def detect_token_from_gh() -> str | None:
    if shutil.which("gh") is None:
        return None
    result = subprocess.run(
        ["gh", "auth", "token"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


def resolve_auth() -> dict[str, str | None]:
    username = os.environ.get("CLI_SYNC_GITHUB_USERNAME", DEFAULT_GITHUB_USERNAME)
    token = None
    for env_name in ("CLI_SYNC_GITHUB_TOKEN", "GITHUB_MCP_PAT", "GH_TOKEN", "GITHUB_TOKEN"):
        env_value = os.environ.get(env_name)
        if env_value:
            token = env_value
            break
    if token is None:
        token = detect_token_from_gh()
    return {
        "username": username,
        "token": token,
    }


def get_remote_url(repo_path: Path, username: str | None, token: str | None) -> str | None:
    result = run_git(repo_path, ["remote", "get-url", "origin"], username=username, token=token, capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def clone_repo_if_missing(repo_path: Path, remote_url: str, username: str | None, token: str | None) -> None:
    if repo_path.exists():
        if not (repo_path / ".git").exists():
            raise RuntimeError(f"Configured repo path exists but is not a git checkout: {repo_path}")
        return
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(None, ["clone", remote_url, str(repo_path)], username=username, token=token, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip() or result.stdout.strip()}")


def discover_repo_path(remote_url: str, username: str | None, token: str | None) -> Path:
    normalized_remote = normalize_remote_url(remote_url)
    env_repo = os.environ.get("CLI_SYNC_REPO_PATH")
    if env_repo:
        candidate = Path(env_repo).expanduser()
        if (candidate / ".git").exists():
            return candidate.resolve()

    script_root = Path(__file__).resolve().parent
    script_repo = find_git_root(script_root)
    if script_repo and normalize_remote_url(get_remote_url(script_repo, username, token)) == normalized_remote:
        return script_repo

    cwd_repo = find_git_root(Path.cwd())
    if cwd_repo and normalize_remote_url(get_remote_url(cwd_repo, username, token)) == normalized_remote:
        return cwd_repo

    repo_path = managed_repo_path()
    clone_repo_if_missing(repo_path, remote_url, username, token)
    return repo_path.resolve()


def ensure_origin_remote(repo_path: Path, remote_url: str, username: str | None, token: str | None) -> None:
    origin_url = get_remote_url(repo_path, username, token)
    if origin_url is None:
        result = run_git(repo_path, ["remote", "add", "origin", remote_url], username=username, token=token, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"git remote add origin failed: {result.stderr.strip() or result.stdout.strip()}")
        return

    if normalize_remote_url(origin_url) != normalize_remote_url(remote_url):
        result = run_git(repo_path, ["remote", "set-url", "origin", remote_url], username=username, token=token, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"git remote set-url origin failed: {result.stderr.strip() or result.stdout.strip()}")


def ensure_branch(repo_path: Path, branch: str, username: str | None, token: str | None) -> None:
    fetch = run_git(repo_path, ["fetch", "origin", branch], username=username, token=token, capture_output=True)
    if fetch.returncode != 0:
        raise RuntimeError(f"git fetch origin {branch} failed: {fetch.stderr.strip() or fetch.stdout.strip()}")

    verify = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", branch],
        check=False,
        text=True,
        capture_output=True,
    )

    if verify.returncode == 0:
        checkout = subprocess.run(
            ["git", "-C", str(repo_path), "checkout", branch],
            check=False,
            text=True,
            capture_output=True,
        )
    else:
        checkout = subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-B", branch, f"origin/{branch}"],
            check=False,
            text=True,
            capture_output=True,
        )

    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout {branch} failed: {checkout.stderr.strip() or checkout.stdout.strip()}")


def git_status(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "status", "--short", "--branch"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def pull_branch(repo_path: Path, branch: str, username: str | None, token: str | None) -> None:
    result = run_git(repo_path, ["pull", "--ff-only", "origin", branch], username=username, token=token, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git pull --ff-only origin {branch} failed: {result.stderr.strip() or result.stdout.strip()}")


def push_branch(repo_path: Path, branch: str, username: str | None, token: str | None) -> None:
    result = run_git(repo_path, ["push", "origin", branch], username=username, token=token, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git push origin {branch} failed: {result.stderr.strip() or result.stdout.strip()}")


def should_skip(path: Path) -> bool:
    return path.name in IGNORE_NAMES or path.suffix in IGNORE_SUFFIXES


def safe_remove_tree(path: Path, root: Path) -> None:
    resolved_root = root.resolve()
    if path.exists():
        resolved_path = path.resolve()
        resolved_path.relative_to(resolved_root)
        shutil.rmtree(resolved_path)


def copy_tree(source: Path, destination: Path) -> None:
    for current_root, dirs, files in os.walk(source):
        root_path = Path(current_root)
        dirs[:] = [name for name in dirs if not should_skip(root_path / name)]
        relative = root_path.relative_to(source)
        target_root = destination / relative
        target_root.mkdir(parents=True, exist_ok=True)

        for file_name in files:
            source_file = root_path / file_name
            if should_skip(source_file):
                continue
            shutil.copy2(source_file, target_root / file_name)


def mirror_tree(source: Path, destination: Path, destination_root: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_remove_tree(destination, destination_root)
    copy_tree(source, destination)
    return True


def sync_local_to_repo(repo_path: Path, skills_path: Path, managed_skills: list[str]) -> list[str]:
    synced: list[str] = []
    skills_root = repo_path / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    for skill in managed_skills:
        if mirror_tree(skills_path / skill, skills_root / skill, skills_root):
            synced.append(skill)
    return synced


def sync_repo_to_local(repo_path: Path, skills_path: Path, managed_skills: list[str]) -> list[str]:
    synced: list[str] = []
    skills_path.mkdir(parents=True, exist_ok=True)
    for skill in managed_skills:
        if mirror_tree(repo_path / "skills" / skill, skills_path / skill, skills_path):
            synced.append(skill)
    return synced


def stage_all(repo_path: Path) -> None:
    result = subprocess.run(["git", "-C", str(repo_path), "add", "-A"], check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git add -A failed: {result.stderr.strip() or result.stdout.strip()}")


def has_staged_changes(repo_path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "diff", "--cached", "--quiet"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise RuntimeError(f"git diff --cached --quiet failed: {result.stderr.strip() or result.stdout.strip()}")


def commit_changes(repo_path: Path, message: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", message],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git commit failed: {result.stderr.strip() or result.stdout.strip()}")


def build_config() -> dict[str, object]:
    auth = resolve_auth()
    username = auth["username"]
    token = auth["token"]
    remote_url = os.environ.get("CLI_SYNC_REMOTE_URL", DEFAULT_REMOTE_URL)
    branch = os.environ.get("CLI_SYNC_BRANCH", DEFAULT_BRANCH)
    skills_path = local_skills_path()
    repo_path = discover_repo_path(remote_url, username, token)
    return {
        "github_username": username,
        "github_token": token,
        "remote_url": remote_url,
        "branch": branch,
        "local_skills_path": skills_path.resolve(),
        "repo_path": repo_path.resolve(),
        "managed_skills": list(DEFAULT_MANAGED_SKILLS),
        "auth_source": "available" if token else "git-or-anonymous",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["status", "pull", "push"], default="status")
    parser.add_argument("--message", default="Sync local Codex skills")
    args = parser.parse_args()

    ensure_git_available()
    config = build_config()

    username = str(config["github_username"])
    token = str(config["github_token"])
    remote_url = str(config["remote_url"])
    branch = str(config["branch"])
    repo_path = Path(config["repo_path"])
    skills_path = Path(config["local_skills_path"])
    managed_skills = list(config["managed_skills"])

    ensure_origin_remote(repo_path, remote_url, username, token)
    ensure_branch(repo_path, branch, username, token)

    result: dict[str, object] = {
        "mode": args.mode,
        "repo_path": str(repo_path),
        "local_skills_path": str(skills_path),
        "remote_url": remote_url,
        "branch": branch,
        "managed_skills": managed_skills,
    }

    if args.mode == "status":
        result["git_status"] = git_status(repo_path)
    elif args.mode == "pull":
        pull_branch(repo_path, branch, username, token)
        result["synced_skills"] = sync_repo_to_local(repo_path, skills_path, managed_skills)
        result["git_status"] = git_status(repo_path)
    else:
        pull_branch(repo_path, branch, username, token)
        result["synced_skills"] = sync_local_to_repo(repo_path, skills_path, managed_skills)
        stage_all(repo_path)
        if has_staged_changes(repo_path):
            commit_changes(repo_path, args.message)
            push_branch(repo_path, branch, username, token)
            result["commit_created"] = True
            result["commit_message"] = args.message
        else:
            result["commit_created"] = False
        result["git_status"] = git_status(repo_path)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
