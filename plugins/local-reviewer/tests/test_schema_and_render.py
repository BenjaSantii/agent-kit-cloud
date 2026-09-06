from __future__ import annotations

import unittest

from local_reviewer.context import ReviewContext
from local_reviewer.render import render_markdown
from local_reviewer.schema import normalize_review


def context() -> ReviewContext:
    return ReviewContext(
        repository="sample",
        root="/tmp/sample",
        target_kind="branch",
        base_ref="main",
        base_sha="base123",
        head_ref="HEAD",
        head_sha="head456",
        branch="feature",
        merge_base="base123",
        title="Fix totals",
        description="",
        pull_request=None,
        pull_request_url=None,
        author=None,
        changed_files=("src/total.py",),
        diff_stat="src/total.py | 2 +−",
        commit_summary="abc Fix totals",
        memory_path=None,
    )


def raw_review() -> dict:
    return {
        "summary": "Se revisó el cálculo de totales.",
        "blockers": [
            {
                "severity": "P1",
                "title": "Conservar el descuento",
                "path": "src/total.py",
                "line": 12,
                "explanation": "El nuevo cálculo elimina el descuento en pedidos parciales.",
                "recommendation": "Aplicar el descuento antes de prorratear.",
            },
            {
                "severity": "P2",
                "title": "External claim",
                "path": "src/old.py",
                "line": 2,
                "explanation": "No cita el cambio.",
                "recommendation": "No publicar.",
            },
        ],
        "suggestions": [],
        "compliance": ["Se inspeccionaron los tests existentes."],
        "coverage": {
            "files_reviewed": ["src/total.py", "src/total.py", "src/context.py"],
            "limitations": ["No se ejecutaron tests."],
        },
        "verdict": "approve",
    }


class SchemaAndRenderTests(unittest.TestCase):
    def test_discards_findings_without_changed_file_evidence_and_derives_verdict(self):
        review, discarded = normalize_review(raw_review(), context().changed_files)

        self.assertEqual(len(review["blockers"]), 1)
        self.assertEqual(len(discarded), 1)
        self.assertEqual(review["verdict"], "request_changes")

    def test_renders_x100_inspired_sections_and_stable_publish_marker(self):
        review, discarded = normalize_review(raw_review(), context().changed_files)

        output = render_markdown(review, context(), provider="codex", discarded=discarded)

        self.assertIn("<!-- local-reviewer:codex:head456 -->", output)
        self.assertIn("🔴 BLOCKERS:", output)
        self.assertIn("🟡 SUGERENCIAS DE DISEÑO Y REFACTOR:", output)
        self.assertIn("🟢 CUMPLIMIENTO Y EXTRAS:", output)
        self.assertIn("📝 VEREDICTO FINAL: Solicitar Cambios", output)
        self.assertIn("src/total.py:12", output)
        self.assertIn("File coverage: `1/1 attested`", output)
        self.assertIn("`P2` defecto concreto de impacto acotado", output)
        self.assertIn("Un `P2` puede bloquear la PR", output)


if __name__ == "__main__":
    unittest.main()
