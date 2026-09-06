from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .context import ReviewContext
from .errors import LocalReviewerError
from .providers import run_review_provider
from .schema import normalize_review


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PLAN_PROMPT_PATH = PLUGIN_ROOT / "prompts" / "ultra-plan.md"
WORKSTREAM_PROMPT_PATH = PLUGIN_ROOT / "prompts" / "ultra-workstream.md"
VERIFY_PROMPT_PATH = PLUGIN_ROOT / "prompts" / "ultra-verify.md"
PLAN_SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "ultra-plan.schema.json"
REVIEW_SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "review.schema.json"


def _render(path: Path, replacements: dict[str, str]) -> str:
    result = path.read_text()
    for key, value in replacements.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def build_plan_prompt(context: ReviewContext, max_passes: int) -> str:
    return _render(
        PLAN_PROMPT_PATH,
        {"REVIEW_CONTEXT": context.prompt_payload(), "MAX_PASSES": str(max_passes)},
    )


def _text(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    return result or fallback


def normalize_plan(raw: object, changed_files: tuple[str, ...], max_passes: int) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("workstreams"), list):
        raise LocalReviewerError("Ultra planner returned an invalid workstream plan.")
    allowed = set(changed_files)
    assigned: set[str] = set()
    workstreams: list[dict[str, Any]] = []
    for index, item in enumerate(raw["workstreams"][:max_passes], start=1):
        if not isinstance(item, dict):
            continue
        files = []
        for value in item.get("files", []):
            path = str(value)
            if path in allowed and path not in assigned:
                files.append(path)
                assigned.add(path)
        if not files:
            continue
        checks = [_text(value, "") for value in item.get("risk_checks", [])]
        workstreams.append(
            {
                "name": _text(item.get("name"), f"Workstream {index}"),
                "objective": _text(item.get("objective"), "Inspect the assigned change deeply."),
                "files": files,
                "risk_checks": [value for value in checks if value],
            }
        )
    if not workstreams:
        workstreams.append(
            {
                "name": "Complete change",
                "objective": "Inspect the complete merge delta and its runtime effects.",
                "files": [],
                "risk_checks": [],
            }
        )
    missing = [path for path in changed_files if path not in assigned]
    for path in missing:
        target = min(workstreams, key=lambda item: len(item["files"]))
        target["files"].append(path)
    cross_checks = [_text(value, "") for value in raw.get("cross_cutting_checks", [])]
    return {
        "summary": _text(raw.get("summary"), "Risk-driven review plan."),
        "workstreams": workstreams,
        "cross_cutting_checks": [value for value in cross_checks if value],
    }


def _merge_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def run_ultra_review(
    provider: str,
    *,
    context: ReviewContext,
    model: str | None,
    timeout: int,
    max_passes: int,
    additional_read_paths: tuple[Path, ...] = (),
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], list[str], int]:
    report = progress or (lambda _message: None)
    report("planning risk workstreams")
    plan_raw = run_review_provider(
        provider,
        root=Path(context.root),
        prompt=build_plan_prompt(context, max_passes),
        schema_path=PLAN_SCHEMA_PATH,
        model=model,
        timeout=timeout,
        additional_read_paths=additional_read_paths,
    )
    plan = normalize_plan(plan_raw, context.changed_files, max_passes)
    candidates: list[dict[str, Any]] = []
    discarded: list[str] = []
    attested_files: list[str] = []
    common = {
        "REVIEW_CONTEXT": context.prompt_payload(),
        "CROSS_CUTTING_CHECKS": json.dumps(plan["cross_cutting_checks"], ensure_ascii=False, indent=2),
    }
    for index, workstream in enumerate(plan["workstreams"], start=1):
        report(f"reviewing workstream {index}/{len(plan['workstreams'])}: {workstream['name']}")
        prompt = _render(
            WORKSTREAM_PROMPT_PATH,
            {**common, "WORKSTREAM": json.dumps(workstream, ensure_ascii=False, indent=2)},
        )
        raw = run_review_provider(
            provider,
            root=Path(context.root),
            prompt=prompt,
            schema_path=REVIEW_SCHEMA_PATH,
            model=model,
            timeout=timeout,
            additional_read_paths=additional_read_paths,
        )
        review, removed = normalize_review(raw, context.changed_files)
        candidates.append(
            {
                "workstream": workstream["name"],
                "summary": review["summary"],
                "blockers": review["blockers"],
                "suggestions": review["suggestions"],
                "limitations": review["coverage"]["limitations"],
            }
        )
        discarded.extend(removed)
        attested_files.extend(review["coverage"]["files_reviewed"])
    report("verifying and consolidating candidate findings")
    verify_prompt = _render(
        VERIFY_PROMPT_PATH,
        {
            "REVIEW_CONTEXT": context.prompt_payload(),
            "REVIEW_PLAN": json.dumps(plan, ensure_ascii=False, indent=2),
            "CANDIDATE_REVIEWS": json.dumps(candidates, ensure_ascii=False, indent=2),
        },
    )
    final_raw = run_review_provider(
        provider,
        root=Path(context.root),
        prompt=verify_prompt,
        schema_path=REVIEW_SCHEMA_PATH,
        model=model,
        timeout=timeout,
        additional_read_paths=additional_read_paths,
    )
    final, removed = normalize_review(final_raw, context.changed_files)
    discarded.extend(removed)
    attested_files.extend(final["coverage"]["files_reviewed"])
    limitations = list(final["coverage"]["limitations"])
    attested = [path for path in _merge_unique(attested_files) if path in set(context.changed_files)]
    missing = [path for path in context.changed_files if path not in set(attested)]
    if missing:
        limitations.append(f"Ultra reviewers did not attest inspection of {len(missing)} changed file(s).")
        if not final["blockers"] and final["verdict"] == "approve":
            final["verdict"] = "comment"
    final["coverage"] = {
        "files_reviewed": attested,
        "limitations": _merge_unique(limitations),
    }
    final["compliance"] = _merge_unique(
        [
            *final["compliance"],
            f"Modo ultra: un plan de riesgo, {len(plan['workstreams'])} revisiones especialistas y una verificación adversarial.",
        ]
    )
    return final, discarded, len(plan["workstreams"]) + 2
