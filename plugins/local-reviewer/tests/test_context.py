from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
