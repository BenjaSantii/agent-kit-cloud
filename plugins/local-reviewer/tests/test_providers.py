from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_reviewer.providers import run_claude, run_codex


REVIEW = {
    "summary": "ok",
    "blockers": [],
    "suggestions": [],
    "compliance": [],
    "coverage": {"files_reviewed": [], "limitations": []},
    "verdict": "approve",
}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.schema = self.root / "schema.json"
        self.schema.write_text('{"type":"object"}')

    def tearDown(self):
        self.temp.cleanup()

    def _executable(self, name: str, body: str) -> None:
        path = self.root / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def test_codex_adapter_reads_output_last_message(self):
        payload = json.dumps(REVIEW)
        self._executable(
            "codex",
            "out=''\nwhile [ $# -gt 0 ]; do\n"
            "  if [ \"$1\" = '--output-last-message' ]; then out=$2; shift 2; else shift; fi\n"
            "done\nprintf '%s' '" + payload + "' > \"$out\"\n",
        )
        with patch.dict(os.environ, {"PATH": f"{self.root}:{os.environ['PATH']}"}):
            result = run_codex(
                root=self.root,
                prompt="review",
                schema_path=self.schema,
                model=None,
                timeout=10,
                additional_read_paths=(self.root / "memory",),
            )

        self.assertEqual(result, REVIEW)

    def test_claude_adapter_reads_structured_output(self):
        envelope = json.dumps({"structured_output": REVIEW})
        self._executable("claude", "cat >/dev/null\nprintf '%s' '" + envelope + "'\n")
        with patch.dict(os.environ, {"PATH": f"{self.root}:{os.environ['PATH']}"}):
            result = run_claude(
                root=self.root,
                prompt="review",
                schema_path=self.schema,
                model=None,
                timeout=10,
                additional_read_paths=(self.root / "memory",),
            )

        self.assertEqual(result, REVIEW)


if __name__ == "__main__":
    unittest.main()
