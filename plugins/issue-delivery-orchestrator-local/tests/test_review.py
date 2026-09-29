import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from issue_delivery_orchestrator.errors import RunBlocked
from issue_delivery_orchestrator.authorship import classify, is_automated
from issue_delivery_orchestrator.review import (
    _is_relevant_bot,
    acknowledge_processed_blocker,
    assert_review_converged,
    publish_skip_summary,
)


class ReviewFilterTests(unittest.TestCase):
    def test_includes_coderabbit_and_only_x100_blockers(self):
        self.assertTrue(
            _is_relevant_bot(
                {"user": {"login": "coderabbitai[bot]"}, "body": "Concrete issue"}
            )
        )
        self.assertTrue(
            _is_relevant_bot(
                {
                    "user": {"login": "x100-production[bot]"},
                    "body": "🔴 BLOCKERS:\n\n- Broken\n\n🟡 SUGERENCIAS:",
                }
            )
        )
        self.assertFalse(
            _is_relevant_bot(
                {
                    "user": {"login": "x100-production[bot]"},
                    "body": "🔴 BLOCKERS:\n\n- Ninguno.\n\n🟡 SUGERENCIAS:",
                }
            )
        )
        self.assertFalse(
            _is_relevant_bot(
                {
                    "user": {"login": "x100-production[bot]"},
                    "body": (
                        "🔴 BLOCKERS:\n\n"
                        "- No encontré defectos funcionales ni regresiones que "
                        "bloqueen la aprobación.\n\n"
                        "🟡 SUGERENCIAS:"
                    ),
                }
            )
        )
        self.assertFalse(
            _is_relevant_bot(
                {"user": {"login": "x100-production[bot]"}, "body": "Refactor suggestion"}
            )
        )
        self.assertFalse(
            _is_relevant_bot(
                {"user": {"login": "human-reviewer"}, "body": "Please change this"}
            )
        )

    def test_treats_x100_verdict_comments_as_blocker_summaries(self):
        header = (
            "PR #10 — [LOG-1] feat(x): y\n\n## Technical review\n\n"
            "## Review identity\n\n- Intensity: `normal`\n\n"
        )
        self.assertTrue(
            _is_relevant_bot(
                {
                    "user": {"login": "x100-production[bot]"},
                    "body": header
                    + "🔴 BLOCKERS:\n\n- `[a.ts:1]` Broken\n\n"
                    + "🟡 SUGERENCIAS DE DISEÑO Y REFACTOR:\n\n- nit",
                }
            )
        )
        self.assertFalse(
            _is_relevant_bot(
                {
                    "user": {"login": "x100-production[bot]"},
                    "body": header
                    + "🔴 BLOCKERS:\n\n- Ninguno.\n\n"
                    + "🟡 SUGERENCIAS DE DISEÑO Y REFACTOR:\n\n- nit\n\n"
                    + "📝 VEREDICTO FINAL: Aprobar",
                }
            )
        )

    def test_acknowledges_processed_blocker_and_records_decision(self):
        with tempfile.TemporaryDirectory() as raw:
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "reviewAcknowledgements": [],
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(number=10)
            client.issue_comment.return_value = {
                "id": 123,
                "issue_url": "https://api.github.com/repos/example/repo/issues/10",
                "html_url": "https://github.com/example/repo/pull/10#issuecomment-123",
                "user": {"login": "x100-production[bot]"},
                "body": "🔴 BLOCKERS:\n\n- Broken\n\n🟡 SUGERENCIAS:",
            }
            client.add_issue_comment_reaction.return_value = True

            with patch(
                "issue_delivery_orchestrator.review.GitHubClient",
                return_value=client,
            ):
                result = acknowledge_processed_blocker(
                    state,
                    comment_id=123,
                    decision="FIX",
                )
                client.add_issue_comment_reaction.return_value = False
                duplicate = acknowledge_processed_blocker(
                    state,
                    comment_id=123,
                    decision="FIX",
                )
                with self.assertRaises(RunBlocked):
                    acknowledge_processed_blocker(
                        state,
                        comment_id=123,
                        decision="SKIP",
                    )

            self.assertTrue(result["created"])
            self.assertFalse(duplicate["created"])
            self.assertEqual(state["reviewAcknowledgements"][0]["decision"], "FIX")
            self.assertTrue(
                state["reviewAcknowledgements"][0]["reactionCreatedInitially"]
            )
            self.assertTrue(state["reviewAcknowledgements"][0]["reactionPresent"])
            self.assertEqual(client.add_issue_comment_reaction.call_count, 2)
            self.assertTrue(
                (
                    Path(raw)
                    / ".local-runtime/issue-delivery-orchestrator/run-1/state.json"
                ).is_file()
            )

    def test_final_gate_rejects_unresolved_inline_and_unacknowledged_general_blockers(
        self,
    ):
        with tempfile.TemporaryDirectory() as raw:
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "artifacts": {},
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(
                number=10,
                url=state["pr"]["url"],
            )
            client.review_threads.return_value = [
                {
                    "id": "thread-1",
                    "isResolved": False,
                    "comments": {
                        "nodes": [
                            {
                                "databaseId": 456,
                                "url": f"{state['pr']['url']}#discussion_r456",
                                "author": {"login": "coderabbitai[bot]"},
                            }
                        ]
                    },
                }
            ]
            client.has_issue_comment_reaction.return_value = False
            snapshot = {
                "headSha": "abc123",
                "botGeneralComments": [
                    {
                        "id": 123,
                        "html_url": f"{state['pr']['url']}#issuecomment-123",
                        "user": {"login": "x100-production[bot]"},
                    }
                ],
            }

            with (
                patch(
                    "issue_delivery_orchestrator.review.GitHubClient",
                    return_value=client,
                ),
                patch(
                    "issue_delivery_orchestrator.review.review_snapshot",
                    return_value=snapshot,
                ),
            ):
                with self.assertRaisesRegex(
                    RunBlocked,
                    r"1 inline thread\(s\), 1 general blocker\(s\)",
                ):
                    assert_review_converged(state)

            receipt_path = (
                Path(raw)
                / ".local-runtime/issue-delivery-orchestrator/run-1/review/final-gate.json"
            )
            self.assertTrue(receipt_path.is_file())
            self.assertEqual(
                state["artifacts"]["finalReviewGate"],
                ".local-runtime/issue-delivery-orchestrator/run-1/review/final-gate.json",
            )

    def test_final_gate_stops_on_human_threads_and_accepts_acknowledged_general_blocker(
        self,
    ):
        with tempfile.TemporaryDirectory() as raw:
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "artifacts": {},
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(
                number=10,
                url=state["pr"]["url"],
            )
            client.review_threads.return_value = [
                {
                    "id": "thread-human",
                    "isResolved": False,
                    "comments": {
                        "nodes": [
                            {
                                "databaseId": 789,
                                "url": f"{state['pr']['url']}#discussion_r789",
                                "author": {"login": "human-reviewer"},
                            }
                        ]
                    },
                }
            ]
            client.has_issue_comment_reaction.return_value = True
            snapshot = {
                "headSha": "abc123",
                "botGeneralComments": [
                    {
                        "id": 123,
                        "html_url": f"{state['pr']['url']}#issuecomment-123",
                        "user": {"login": "x100-production[bot]"},
                    }
                ],
            }

            with (
                patch(
                    "issue_delivery_orchestrator.review.GitHubClient",
                    return_value=client,
                ),
                patch(
                    "issue_delivery_orchestrator.review.review_snapshot",
                    return_value=snapshot,
                ),
            ):
                with self.assertRaisesRegex(
                    RunBlocked,
                    r"unresolved human feedback .* human-reviewer",
                ):
                    assert_review_converged(state)

            receipt = json.loads(
                (
                    Path(raw)
                    / ".local-runtime/issue-delivery-orchestrator/run-1"
                    / "review/final-gate.json"
                ).read_text()
            )
            self.assertFalse(receipt["passed"])
            self.assertEqual(receipt["pendingInlineThreads"], [])
            self.assertEqual(receipt["pendingGeneralBlockers"], [])
            self.assertEqual(
                [item["author"] for item in receipt["pendingHumanFeedback"]],
                ["human-reviewer"],
            )

    def test_classifies_by_body_marker_not_by_author_login(self):
        codex_under_human_login = {
            "user": {"login": "x100-production"},
            "body": (
                "Codex Code Review\n"
                "Task: SFW-1428 — resolve UI bugs\n\n"
                "🔴 BLOCKERS:\n\n- El contador se rompe al filtrar.\n\n"
                "🟡 SUGERENCIAS:"
            ),
        }
        self.assertTrue(is_automated(codex_under_human_login))
        self.assertEqual(
            classify(codex_under_human_login).signal,
            "body-signature",
        )
        self.assertTrue(_is_relevant_bot(codex_under_human_login))

        codex_under_human_login_without_blockers = {
            "user": {"login": "x100-production"},
            "body": (
                "Codex Code Review\n"
                "Task: SFW-1428 — resolve UI bugs\n\n"
                "🔴 BLOCKERS:\n\n- Ninguno.\n\n🟡 SUGERENCIAS:"
            ),
        }
        self.assertFalse(_is_relevant_bot(codex_under_human_login_without_blockers))

        human_talking_about_bots = {
            "user": {"login": "x100-production"},
            "body": "Ojo que el codex code review de ayer se equivocó acá.",
        }
        self.assertFalse(is_automated(human_talking_about_bots))
        self.assertEqual(classify(human_talking_about_bots).source, "human")

    def test_publishes_summary_only_when_all_pending_feedback_is_skip(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            input_path = root / "skips.json"
            input_path.write_text(
                json.dumps(
                    {
                        "skips": [
                            {
                                "commentId": 123,
                                "title": "Fallback innecesario",
                                "reason": "El flujo vigente ya cubre este caso.",
                            },
                            {
                                "commentId": 456,
                                "title": "Generalización fuera de alcance",
                                "reason": "No existe un requisito actual para soportarla.",
                            },
                        ]
                    }
                )
            )
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "artifacts": {},
                "reviewAcknowledgements": [],
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(
                number=10,
                url=state["pr"]["url"],
            )
            client.review_threads.return_value = [
                {
                    "id": "thread-1",
                    "isResolved": False,
                    "comments": {
                        "nodes": [
                            {
                                "databaseId": 456,
                                "url": f"{state['pr']['url']}#discussion_r456",
                                "author": {"login": "coderabbitai[bot]"},
                            }
                        ]
                    },
                }
            ]
            client.has_issue_comment_reaction.return_value = False
            client.upsert_comment.return_value = (
                f"{state['pr']['url']}#issuecomment-summary"
            )
            snapshot = {
                "headSha": "abc123",
                "botGeneralComments": [
                    {
                        "id": 123,
                        "html_url": f"{state['pr']['url']}#issuecomment-123",
                        "user": {"login": "x100-production[bot]"},
                    }
                ],
            }

            with (
                patch(
                    "issue_delivery_orchestrator.review.GitHubClient",
                    return_value=client,
                ),
                patch(
                    "issue_delivery_orchestrator.review.review_snapshot",
                    return_value=snapshot,
                ),
            ):
                result = publish_skip_summary(state, input_path=input_path)
                client.review_threads.return_value = []
                snapshot["botGeneralComments"] = []
                repeated = publish_skip_summary(state, input_path=input_path)

            self.assertEqual(result["commentIds"], [123, 456])
            self.assertEqual(repeated["commentIds"], [123, 456])
            body = client.upsert_comment.call_args.args[2]
            self.assertIn("Fallback innecesario", body)
            self.assertIn("El flujo vigente ya cubre este caso.", body)
            self.assertIn("issue-delivery-skip-summary:run-1", body)
            self.assertEqual(state["skipSummary"]["commentIds"], [123, 456])
            self.assertEqual(client.upsert_comment.call_count, 2)

    def test_rejects_skip_summary_missing_a_pending_blocker(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            input_path = root / "skips.json"
            input_path.write_text(
                json.dumps(
                    {
                        "skips": [
                            {
                                "commentId": 123,
                                "reason": "No corresponde al alcance.",
                            }
                        ]
                    }
                )
            )
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "artifacts": {},
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(
                number=10,
                url=state["pr"]["url"],
            )
            client.review_threads.return_value = [
                {
                    "id": "thread-1",
                    "isResolved": False,
                    "comments": {
                        "nodes": [
                            {
                                "databaseId": 456,
                                "url": f"{state['pr']['url']}#discussion_r456",
                                "author": {"login": "coderabbitai[bot]"},
                            }
                        ]
                    },
                }
            ]
            client.has_issue_comment_reaction.return_value = False
            snapshot = {
                "headSha": "abc123",
                "botGeneralComments": [
                    {
                        "id": 123,
                        "html_url": f"{state['pr']['url']}#issuecomment-123",
                        "user": {"login": "x100-production[bot]"},
                    }
                ],
            }

            with (
                patch(
                    "issue_delivery_orchestrator.review.GitHubClient",
                    return_value=client,
                ),
                patch(
                    "issue_delivery_orchestrator.review.review_snapshot",
                    return_value=snapshot,
                ),
            ):
                with self.assertRaisesRegex(RunBlocked, r"missing=\[456\]"):
                    publish_skip_summary(state, input_path=input_path)

            client.upsert_comment.assert_not_called()

    def test_rejects_acknowledging_skip_before_public_summary(self):
        with tempfile.TemporaryDirectory() as raw:
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "reviewAcknowledgements": [],
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(number=10)
            client.issue_comment.return_value = {
                "id": 123,
                "issue_url": "https://api.github.com/repos/example/repo/issues/10",
                "html_url": "https://github.com/example/repo/pull/10#issuecomment-123",
                "user": {"login": "x100-production[bot]"},
                "body": "🔴 BLOCKERS:\n\n- Broken\n\n🟡 SUGERENCIAS:",
            }

            with patch(
                "issue_delivery_orchestrator.review.GitHubClient",
                return_value=client,
            ):
                with self.assertRaisesRegex(RunBlocked, "publish-skip-summary"):
                    acknowledge_processed_blocker(
                        state,
                        comment_id=123,
                        decision="SKIP",
                    )

            client.add_issue_comment_reaction.assert_not_called()

    def test_final_gate_rejects_legacy_skip_without_public_summary(self):
        with tempfile.TemporaryDirectory() as raw:
            state = {
                "worktree": raw,
                "runId": "run-1",
                "pr": {"url": "https://github.com/example/repo/pull/10"},
                "artifacts": {},
                "reviewAcknowledgements": [
                    {
                        "commentId": 123,
                        "commentUrl": (
                            "https://github.com/example/repo/pull/10#issuecomment-123"
                        ),
                        "decision": "SKIP",
                    }
                ],
            }
            client = Mock()
            client.view.return_value = SimpleNamespace(
                number=10,
                url=state["pr"]["url"],
            )
            client.review_threads.return_value = []
            snapshot = {"headSha": "abc123", "botGeneralComments": []}

            with (
                patch(
                    "issue_delivery_orchestrator.review.GitHubClient",
                    return_value=client,
                ),
                patch(
                    "issue_delivery_orchestrator.review.review_snapshot",
                    return_value=snapshot,
                ),
            ):
                with self.assertRaisesRegex(
                    RunBlocked,
                    r"1 unpublished SKIP acknowledgement\(s\)",
                ):
                    assert_review_converged(state)


if __name__ == "__main__":
    unittest.main()
