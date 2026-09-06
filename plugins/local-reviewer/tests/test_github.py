from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_reviewer.context import ReviewContext
from local_reviewer.github import publish_comment


def context() -> ReviewContext:
    return ReviewContext(
        repository="sample",
        root="/tmp/sample",
        target_kind="pull_request",
        base_ref="origin/main",
        base_sha="base",
        head_ref="feature",
        head_sha="head",
        branch="feature",
        merge_base="base",
        title="PR",
        description="",
        pull_request=7,
        pull_request_url="https://github.com/acme/sample/pull/7",
        author="author",
        changed_files=("app.py",),
        diff_stat="",
        commit_summary="",
        memory_path=None,
    )


class GithubTests(unittest.TestCase):
    def test_updates_only_a_matching_comment_owned_by_current_user(self):
        marker = "<!-- local-reviewer:codex:head -->"
        responses = [
            SimpleNamespace(stdout=json.dumps({"nameWithOwner": "acme/sample"})),
            SimpleNamespace(
                stdout=json.dumps(
                    [
                        [
                            {"id": 10, "body": marker, "user": {"login": "someone-else"}},
                            {"id": 11, "body": marker, "user": {"login": "reviewer"}},
                        ]
                    ]
                )
            ),
            SimpleNamespace(stdout=json.dumps({"login": "reviewer"})),
            SimpleNamespace(stdout=json.dumps({"html_url": "https://github.com/acme/sample/pull/7#comment"})),
        ]
        with patch("local_reviewer.github.run", side_effect=responses) as mocked:
            url = publish_comment(context(), marker + "\nReview", provider="codex")

        command = mocked.call_args_list[-1].args[0]
        self.assertIn("PATCH", command)
        self.assertIn("repos/acme/sample/issues/comments/11", command)
        self.assertEqual(url, "https://github.com/acme/sample/pull/7#comment")


if __name__ == "__main__":
    unittest.main()
