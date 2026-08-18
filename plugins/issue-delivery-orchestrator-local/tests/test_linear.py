import tempfile
import unittest
from pathlib import Path

from issue_delivery_orchestrator.errors import OrchestrationError
from issue_delivery_orchestrator.evidence import upsert_ui_run
from issue_delivery_orchestrator.linear import (
    LinearClient,
    extract_marker_block,
    linear_markdown_equivalent,
    normalize_issue_identifier,
    normalize_linear_markdown,
    upsert_markdown_section,
    upsert_marker_block,
)


class LinearHelpersTests(unittest.TestCase):
    def test_fetches_all_issue_comments_with_cursor_pagination(self):
        class Client(LinearClient):
            def __init__(self):
                super().__init__("secret")
                self.afters = []

            def _graphql(self, query, variables):
                self.assert_query(query)
                self.afters.append(variables["after"])
                if variables["after"] is None:
                    return {
                        "issue": {
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "comment-1",
                                        "body": "First",
                                        "createdAt": "2026-08-01T00:00:00Z",
                                        "updatedAt": "2026-08-01T00:00:00Z",
                                        "user": {
                                            "id": "user-1",
                                            "name": "Benjamin",
                                            "displayName": "Benja",
                                        },
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "cursor-2",
                                },
                            }
                        }
                    }
                return {
                    "issue": {
                        "comments": {
                            "nodes": [
                                {
                                    "id": "comment-2",
                                    "body": "Second",
                                    "createdAt": "2026-08-02T00:00:00Z",
                                    "updatedAt": "2026-08-02T00:00:00Z",
                                    "user": None,
                                }
                            ],
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                        }
                    }
                }

            def assert_query(self, query):
                if "comments(first: 50, after: $after)" not in query:
                    raise AssertionError(query)

        client = Client()

        comments = client.issue_comments("issue-id")

        self.assertEqual(client.afters, [None, "cursor-2"])
        self.assertEqual([comment.id for comment in comments], ["comment-1", "comment-2"])
        self.assertEqual(comments[0].user_display_name, "Benja")
        self.assertEqual(comments[1].user_id, "")

    def test_normalizes_identifier_and_linear_url(self):
        self.assertEqual(normalize_issue_identifier("ts-123"), "TS-123")
        self.assertEqual(
            normalize_issue_identifier("https://linear.app/turboshop/issue/TS-456/a-title"),
            "TS-456",
        )

    def test_rejects_non_issue_value(self):
        with self.assertRaises(OrchestrationError):
            normalize_issue_identifier("not-an-issue")

    def test_upserts_named_section_without_touching_following_section(self):
        source = "# Issue\n\n## Spec\n\nOld\n\n## Tickets\n\nKeep\n"
        updated = upsert_markdown_section(source, "Spec", "New")
        self.assertIn("## Spec\n\nNew", updated)
        self.assertIn("## Tickets\n\nKeep", updated)
        self.assertNotIn("\nOld\n", updated)

    def test_upserts_only_current_ui_run(self):
        source = (
            "Intro\n\n## UI enhancements\n\n"
            "### Issue Delivery old\n\nold-image\n\n"
            "### Issue Delivery current\n\nstale\n\n"
            "## Tickets\n\nKeep\n"
        )
        updated = upsert_ui_run(
            source,
            "current",
            "### Issue Delivery current\n\nfresh",
        )
        self.assertIn("old-image", updated)
        self.assertIn("fresh", updated)
        self.assertNotIn("stale", updated)
        self.assertIn("## Tickets\n\nKeep", updated)

    def test_upserts_marker_block_without_touching_other_content(self):
        source = (
            "Intro\n\n<!-- loop:spec:start -->\nOld\n<!-- loop:spec:end -->"
            "\n\nKeep"
        )
        updated = upsert_marker_block(
            source,
            marker_prefix="loop",
            block="spec",
            body="New",
        )

        self.assertIn("<!-- loop:spec:start -->\nNew\n<!-- loop:spec:end -->", updated)
        self.assertIn("Keep", updated)
        self.assertNotIn("\nOld\n", updated)

    def test_rejects_inconsistent_marker_block(self):
        with self.assertRaisesRegex(OrchestrationError, "inconsistent spec markers"):
            upsert_marker_block(
                "<!-- loop:spec:start -->\nMissing end",
                marker_prefix="loop",
                block="spec",
                body="New",
            )

    def test_extracts_only_content_between_marker_pair(self):
        document = (
            "Before\n<!-- loop:spec:start -->\nExpected\n"
            "<!-- loop:spec:end -->\nAfter"
        )

        extracted = extract_marker_block(
            document,
            marker_prefix="loop",
            block="spec",
        )

        self.assertEqual(extracted, "Expected")

    def test_normalizes_linear_bullets_and_table_separators(self):
        local = (
            "- First\n  - Nested\n\n"
            "| Name | Decision |\n| --- | :---: |\n| Snapshot | Keep |"
        )
        remote = (
            "* First\n  * Nested\n\n"
            "| Name | Decision |\n|:-----|------:|\n| Snapshot | Keep |"
        )

        self.assertTrue(linear_markdown_equivalent(local, remote))
        self.assertEqual(
            normalize_linear_markdown(local),
            normalize_linear_markdown(remote),
        )

    def test_normalizes_linear_short_table_separators_and_edge_fragments(self):
        local = "- | --- | --- | --- | --- | -"
        remote = " | -- | -- | -- | -- | "

        self.assertTrue(linear_markdown_equivalent(local, remote))
        self.assertEqual(
            normalize_linear_markdown(local),
            "| --- | --- | --- | --- |",
        )

    def test_table_separator_normalization_preserves_column_count(self):
        expected = "| --- | --- | --- |"
        changed = "| -- | -- |"

        self.assertFalse(linear_markdown_equivalent(expected, changed))

    def test_table_separator_normalization_rejects_content_cells(self):
        expected = "| --- | changed | --- |"

        self.assertEqual(normalize_linear_markdown(expected), expected)

    def test_normalizes_linear_blank_line_before_list_after_label(self):
        local = "Blocked by:\n- TICKET-001"
        remote = "Blocked by:\n\n* TICKET-001"

        self.assertTrue(linear_markdown_equivalent(local, remote))

    def test_list_spacing_normalization_preserves_unrelated_blank_lines(self):
        expected = "Paragraph\n- Item"
        changed = "Paragraph\n\n- Item"

        self.assertFalse(linear_markdown_equivalent(expected, changed))

    def test_normalization_preserves_material_markdown_differences(self):
        expected = "- Persist rejected snapshots\n| Field | Value |\n| --- | --- |"
        changed = "* Persist every snapshot\n| Field | Value |\n| --- | --- |"

        self.assertFalse(linear_markdown_equivalent(expected, changed))


if __name__ == "__main__":
    unittest.main()
