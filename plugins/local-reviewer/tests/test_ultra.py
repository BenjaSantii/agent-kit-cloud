from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from local_reviewer.context import ReviewContext
from local_reviewer.ultra import normalize_plan, run_ultra_review


def context() -> ReviewContext:
    return ReviewContext(
        repository="repo",
        root="/tmp/repo",
        target_kind="pull_request",
        base_ref="origin/main",
        base_sha="base",
        head_ref="feature",
        head_sha="head",
        branch="feature",
        merge_base="base",
        title="Critical change",
        description="",
        pull_request=1,
        pull_request_url="https://example.test/pull/1",
        author="reviewer",
        changed_files=("a.py", "b.py", "c.py"),
        diff_stat="3 files changed",
        commit_summary="change",
        memory_path=None,
    )


def review(files, *, blockers=None, verdict="approve"):
    return {
        "summary": "reviewed",
        "blockers": blockers or [],
        "suggestions": [],
        "compliance": [],
        "coverage": {"files_reviewed": files, "limitations": []},
        "verdict": verdict,
    }


class UltraTests(unittest.TestCase):
    def test_plan_assigns_omitted_files_exactly_once(self):
        plan = normalize_plan(
            {
                "summary": "plan",
                "workstreams": [
                    {"name": "A", "objective": "A", "files": ["a.py"], "risk_checks": []},
                    {"name": "B", "objective": "B", "files": ["a.py", "b.py"], "risk_checks": []},
                ],
                "cross_cutting_checks": [],
            },
            ("a.py", "b.py", "c.py"),
            2,
        )

        assigned = [path for item in plan["workstreams"] for path in item["files"]]
        self.assertCountEqual(assigned, ["a.py", "b.py", "c.py"])

    def test_ultra_runs_plan_specialists_and_adversarial_verifier(self):
        candidate = {
            "severity": "P1",
            "title": "Broken path",
            "path": "a.py",
            "line": 1,
            "explanation": "The path fails.",
            "recommendation": "Preserve the path.",
        }
        first_specialist = review(["a.py", "b.py"], blockers=[candidate], verdict="request_changes")
        first_specialist["coverage"]["limitations"] = ["specialist detail"]
        final_review = review(["a.py", "b.py", "c.py"], blockers=[candidate], verdict="request_changes")
        final_review["coverage"]["limitations"] = ["consolidated limitation"]
        responses = [
            {
                "summary": "plan",
                "workstreams": [
                    {"name": "A", "objective": "A", "files": ["a.py", "b.py"], "risk_checks": []},
                    {"name": "B", "objective": "B", "files": ["c.py"], "risk_checks": []},
                ],
                "cross_cutting_checks": ["contracts"],
            },
            first_specialist,
            review(["c.py"]),
            final_review,
        ]
        with patch("local_reviewer.ultra.run_review_provider", side_effect=responses) as provider:
            result, discarded, pass_count = run_ultra_review(
                "codex",
                context=context(),
                model=None,
                timeout=10,
                max_passes=2,
                additional_read_paths=(Path("/tmp/memory"),),
            )

        self.assertEqual(provider.call_count, 4)
        self.assertEqual(pass_count, 4)
        self.assertEqual(result["blockers"], [candidate])
        self.assertCountEqual(result["coverage"]["files_reviewed"], ["a.py", "b.py", "c.py"])
        self.assertEqual(result["coverage"]["limitations"], ["consolidated limitation"])
        self.assertEqual(discarded, [])
        self.assertIn("Modo ultra", result["compliance"][0])


if __name__ == "__main__":
    unittest.main()
