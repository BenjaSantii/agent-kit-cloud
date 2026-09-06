from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .context import ReviewContext


VERDICT_LABELS = {
    "approve": "Aprobar",
    "comment": "Comentar",
    "request_changes": "Solicitar Cambios",
}


def _finding(item: dict[str, Any]) -> str:
    location = item["path"]
    if item.get("line"):
        location += f":{item['line']}"
    return (
        f"- `[{item['severity']}]` `[{location}]` **{item['title']}** — "
        f"{item['explanation']} Recomendación: {item['recommendation']}"
    )


def render_markdown(
    review: dict[str, Any],
    context: ReviewContext,
    *,
    provider: str,
    mode: str = "standard",
    pass_count: int = 1,
    discarded: list[str] | None = None,
) -> str:
    run_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    marker = f"<!-- local-reviewer:{provider}:{context.head_sha} -->"
    files_reviewed = len(set(review["coverage"]["files_reviewed"]) & set(context.changed_files))
    lines = [
        marker,
        f"# {context.title}",
        "",
        "## Technical review",
        "",
        review["summary"],
        "",
        "## Review identity",
        "",
        f"- Run: `{run_id}`",
        f"- Timestamp: `{timestamp}`",
        f"- Provider: `{provider}`",
        f"- Mode: `{mode}`",
        f"- Provider passes: `{pass_count}`",
        f"- Head: `{context.head_sha}`",
        f"- Base: `{context.base_sha or context.base_ref}`",
        f"- Branches: `{context.branch} → {context.base_ref}`",
        f"- Target: `{context.target_kind}`",
        f"- File coverage: `{files_reviewed}/{len(context.changed_files)} attested`",
        "",
        "**Escala:** `P0` crítico · `P1` grave/urgente · `P2` defecto concreto de impacto acotado · `P3` mejora no bloqueante. Un `P2` puede bloquear la PR si incumple su objetivo.",
        "",
        "🔴 BLOCKERS:",
    ]
    lines.extend(_finding(item) for item in review["blockers"])
    if not review["blockers"]:
        lines.append("- Ninguno.")
    lines.extend(["", "🟡 SUGERENCIAS DE DISEÑO Y REFACTOR:"])
    lines.extend(_finding(item) for item in review["suggestions"])
    if not review["suggestions"]:
        lines.append("- Ninguna.")
    lines.extend(["", "🟢 CUMPLIMIENTO Y EXTRAS:"])
    lines.extend(f"- {item}" for item in review["compliance"])
    for limitation in review["coverage"]["limitations"]:
        lines.append(f"- Limitación: {limitation}")
    if discarded:
        lines.append(
            f"- El controlador descartó {len(discarded)} hallazgo(s) cuya cita no apuntaba a un archivo modificado."
        )
    if not review["compliance"] and not review["coverage"]["limitations"] and not discarded:
        lines.append("- Sin observaciones adicionales.")
    lines.extend(["", f"📝 VEREDICTO FINAL: {VERDICT_LABELS[review['verdict']]}"])
    return "\n".join(lines).rstrip() + "\n"
