#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import repo


def local_git(*args, cwd=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid", GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")
    r = subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)
    return r.stdout.strip()


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.root = self.base / "Workspace"
        self.source = self.base / "source"; self.source.mkdir()
        local_git("init", "-b", "main", cwd=self.source)
        (self.source / "README.md").write_text("hello\n")
        local_git("add", ".", cwd=self.source); local_git("commit", "-m", "initial", cwd=self.source)
        self.url = "https://github.com/example/project.git"
        self.child = "https://github.com/example/downloads.git"
        original = repo.git
        def mapped(args, directory=None, check=True):
            if args[0] == "clone" and args[-2] in (self.url, self.child):
                requested = args[-2]; args = list(args); args[-2] = str(self.source)
                r = original(args, directory, check)
                if r.returncode == 0:
                    original(["remote", "set-url", "origin", requested], args[-1])
                return r
            return original(args, directory, check)
        self.addCleanup(patch.stopall)
        patch.object(repo, "git", side_effect=mapped).start()
        patch.object(repo, "git_environment", return_value=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid", GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")).start()

    def test_nested_clone_idempotence_and_no_existing_changes(self):
        entries = [{"url": self.child, "path": "project/release"}, {"url": self.url, "path": "project"}]
        self.assertEqual([x["status"] for x in repo.ensure_repositories(entries, self.root)], ["cloned", "cloned"])
        target = self.root / "project"
        (target / "README.md").write_text("uncommitted\n")
        before = local_git("status", "--porcelain", cwd=target)
        head = local_git("rev-parse", "HEAD", cwd=target)
        with patch.object(repo, "git", wraps=repo.git) as spy:
            self.assertEqual([x["status"] for x in repo.ensure_repositories(entries, self.root)], ["existing", "existing"])
            self.assertFalse(any(call.args[0][0] in ("fetch", "pull", "commit", "push") for call in spy.call_args_list))
        self.assertEqual(before, local_git("status", "--porcelain", cwd=target))
        self.assertEqual(head, local_git("rev-parse", "HEAD", cwd=target))

    def test_conflict_parent_blocks_nested_clone(self):
        (self.root / "project").mkdir(parents=True)
        sentinel = self.root / "project" / "keep"; sentinel.write_text("keep")
        entries = [{"url": self.url, "path": "project"}, {"url": self.child, "path": "project/release"}]
        self.assertEqual([x["status"] for x in repo.ensure_repositories(entries, self.root)], ["conflict", "conflict"])
        self.assertFalse((self.root / "project/release").exists()); self.assertEqual(sentinel.read_text(), "keep")

    def test_remote_mismatch_and_failed_clone(self):
        entry = {"url": self.url, "path": "project"}
        repo.ensure_repositories([entry], self.root)
        local_git("remote", "set-url", "origin", self.child, cwd=self.root / "project")
        self.assertEqual(repo.ensure_repositories([entry], self.root)[0]["status"], "conflict")
        def fail(*args, **kwargs): raise RuntimeError("authentication unavailable")
        with patch.object(repo, "git", side_effect=fail):
            self.assertEqual(repo.ensure_repositories([{**entry, "path": "absent"}], self.root)[0]["status"], "failed")
        self.assertFalse((self.root / "absent").exists())

    def test_url_and_directory_validation(self):
        self.assertEqual(repo.normalize_url("git@github.com:example/project.git"), self.url)
        for value in ("https://token@github.com/example/project", "https://evil.invalid/example/project", "https://github.com/example/project?token=secret"):
            with self.assertRaises(ValueError): repo.normalize_url(value)
        for path in ("../outside", "project/../outside", "/absolute", "D:/Other", "project/.git/x", "a\\b"):
            with self.assertRaises(ValueError): repo.validate_catalog({"repositories": [{"url": self.url, "path": path}]})
        with patch.object(repo.sys, "platform", "win32"):
            self.assertEqual(str(repo.workspace_root()), "D:/Workspace")

    def test_discover_and_register_preserves_other_checkout(self):
        target = self.root / "project"; target.parent.mkdir(parents=True)
        local_git("clone", str(self.source), str(target)); local_git("remote", "set-url", "origin", self.url, cwd=target)
        entry = repo.discover_project(target, self.root)
        self.assertEqual(entry, {"url": self.url, "path": "project"})
        catalog = self.base / "catalog"; catalog.mkdir(); local_git("init", "-b", "main", cwd=catalog)
        path = catalog / repo.CATALOG_PATH; path.parent.mkdir(parents=True)
        path.write_text('{"repositories": []}\n'); local_git("add", ".", cwd=catalog); local_git("commit", "-m", "catalog", cwd=catalog)
        bare = self.base / "catalog.git"; local_git("clone", "--bare", str(catalog), str(bare))
        (catalog / "unrelated.txt").write_text("preserve")
        local_copy = self.base / "local.json"
        with patch.object(repo, "CATALOG_REPO", str(bare)), patch.object(repo, "LOCAL_CATALOG", local_copy):
            self.assertEqual(repo.register_project(entry)["status"], "registered")
            self.assertEqual(repo.register_project(entry)["status"], "already_registered")
            self.assertEqual(repo.read_remote_catalog(), [entry])
        self.assertEqual((catalog / "unrelated.txt").read_text(), "preserve")
        self.assertEqual(json.loads(local_copy.read_text())["repositories"], [entry])


if __name__ == "__main__":
    unittest.main()
