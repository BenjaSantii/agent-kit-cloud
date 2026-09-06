from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import local_reviewer.context as context_module
from local_reviewer.context import collect_context


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "reviewer@example.com")
        git(self.root, "config", "user.name", "Reviewer")
        (self.root / "app.py").write_text("value = 1\n")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-m", "initial")

    def tearDown(self):
        self.temp.cleanup()

    def test_collects_merge_delta_from_explicit_base(self):
        git(self.root, "switch", "-c", "feature")
        (self.root / "app.py").write_text("value = 2\n")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-m", "change value")

        context = collect_context(self.root, base="main", auto_pull_request=False)

        self.assertEqual(context.target_kind, "branch")
        self.assertEqual(context.changed_files, ("app.py",))
        self.assertEqual(context.merge_base, git(self.root, "rev-parse", "main"))
        self.assertIn("change value", context.commit_summary)

    def test_uncommitted_scope_includes_untracked_files(self):
        (self.root / "app.py").write_text("value = 3\n")
        (self.root / "new.py").write_text("new = True\n")

        context = collect_context(self.root, uncommitted=True, auto_pull_request=False)

        self.assertEqual(context.target_kind, "uncommitted")
        self.assertEqual(set(context.changed_files), {"app.py", "new.py"})

    def test_pr_file_inventory_comes_from_git_without_api_pagination(self):
        base_sha = git(self.root, "rev-parse", "HEAD")
        git(self.root, "switch", "-c", "feature")
        for index in range(105):
            (self.root / f"file-{index:03}.txt").write_text(f"{index}\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "large change")
        head_sha = git(self.root, "rev-parse", "HEAD")
        original_run = context_module.run

        def fake_run(args, *, cwd, input_text=None, check=True):
            if args[:3] == ["gh", "pr", "view"]:
                payload = {
                    "number": 123,
                    "title": "Large PR",
                    "body": "",
                    "url": "https://example.test/pull/123",
                    "baseRefName": "main",
                    "baseRefOid": base_sha,
                    "headRefName": "feature",
                    "headRefOid": head_sha,
                    "author": {"login": "reviewer"},
                    "commits": [],
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            return original_run(args, cwd=cwd, input_text=input_text, check=check)

        with patch.object(context_module, "run", side_effect=fake_run):
            context = collect_context(self.root, pull_request=123)

        self.assertEqual(len(context.changed_files), 105)
        self.assertIn("file-104.txt", context.changed_files)


if __name__ == "__main__":
    unittest.main()
