from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import LocalReviewerError


REQUIRED_TOP_LEVEL = {"summary", "blockers", "suggestions", "compliance", "coverage", "verdict"}


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _normalize_finding(item: object, *, category: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise LocalReviewerError(f"Every {category} finding must be an object.")
    required = {"severity", "title", "path", "line", "explanation", "recommendation"}
    missing = required - set(item)
    if missing:
        raise LocalReviewerError(f"A {category} finding is missing: {', '.join(sorted(missing))}.")
    severity = str(item["severity"])
    allowed = {"P0", "P1", "P2"} if category == "blocker" else {"P2", "P3"}
    if severity not in allowed:
        raise LocalReviewerError(f"Invalid {category} severity: {severity}.")
    line = item["line"]
    if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
        raise LocalReviewerError("Finding line must be a positive integer or null.")
    normalized = {key: item[key] for key in required}
    for key in ("title", "path", "explanation", "recommendation"):
        normalized[key] = str(normalized[key]).strip()
        if not normalized[key]:
            raise LocalReviewerError(f"Finding {key} cannot be empty.")
    return normalized


def normalize_review(raw: object, changed_files: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(raw, dict):
        raise LocalReviewerError("Provider did not return a JSON review object.")
    missing = REQUIRED_TOP_LEVEL - set(raw)
    if missing:
        raise LocalReviewerError(f"Review is missing: {', '.join(sorted(missing))}.")
    if not isinstance(raw["blockers"], list) or not isinstance(raw["suggestions"], list):
        raise LocalReviewerError("Review blockers and suggestions must be arrays.")
    if not isinstance(raw["compliance"], list):
        raise LocalReviewerError("Review compliance must be an array.")
    review: dict[str, Any] = {
        "summary": str(raw["summary"]).strip(),
        "blockers": [_normalize_finding(item, category="blocker") for item in raw["blockers"]],
        "suggestions": [_normalize_finding(item, category="suggestion") for item in raw["suggestions"]],
        "compliance": [str(item).strip() for item in raw["compliance"] if str(item).strip()],
        "coverage": raw["coverage"],
        "verdict": str(raw["verdict"]),
    }
    if not review["summary"]:
        raise LocalReviewerError("Review summary cannot be empty.")
    if not isinstance(review["coverage"], dict):
        raise LocalReviewerError("Review coverage must be an object.")
    reviewed = review["coverage"].get("files_reviewed", [])
    limitations = review["coverage"].get("limitations", [])
    if not isinstance(reviewed, list) or not isinstance(limitations, list):
        raise LocalReviewerError("Coverage files_reviewed and limitations must be arrays.")
    review["coverage"] = {
        "files_reviewed": [str(item) for item in reviewed],
        "limitations": [str(item) for item in limitations if str(item).strip()],
    }
    changed = set(changed_files)
    discarded: list[str] = []
    for category in ("blockers", "suggestions"):
        supported = []
        for finding in review[category]:
            if changed and finding["path"] not in changed:
                discarded.append(f"{finding['path']}: {finding['title']}")
                continue
            supported.append(finding)
        review[category] = supported
    verdicts = {"approve", "comment", "request_changes"}
    if review["verdict"] not in verdicts:
        raise LocalReviewerError(f"Invalid verdict: {review['verdict']}.")
    review["verdict"] = "request_changes" if review["blockers"] else (
        "comment" if review["verdict"] == "request_changes" else review["verdict"]
    )
    return review, discarded
