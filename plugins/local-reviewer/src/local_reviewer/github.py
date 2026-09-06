from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .context import ReviewContext, run
from .errors import LocalReviewerError


def publish_comment(context: ReviewContext, body: str, *, provider: str) -> str:
    if context.pull_request is None:
        raise LocalReviewerError("GitHub publication requires a pull-request target; pass --pr or run from a PR branch.")
    root = Path(context.root)
    repository = json.loads(run(["gh", "repo", "view", "--json", "nameWithOwner"], cwd=root).stdout)[
        "nameWithOwner"
    ]
    endpoint = f"repos/{repository}/issues/{context.pull_request}/comments"
    pages = json.loads(
        run(["gh", "api", "--paginate", "--slurp", f"{endpoint}?per_page=100"], cwd=root).stdout
    )
    comments = [item for page in pages for item in page]
    current_login = json.loads(run(["gh", "api", "user"], cwd=root).stdout)["login"]
    marker = f"<!-- local-reviewer:{provider}:{context.head_sha} -->"
    existing: dict[str, Any] | None = next(
        (
            item
            for item in comments
            if marker in str(item.get("body") or "")
            and (item.get("user") or {}).get("login") == current_login
        ),
        None,
    )
    if existing:
        result = run(
            ["gh", "api", "--method", "PATCH", f"repos/{repository}/issues/comments/{existing['id']}", "-f", f"body={body}"],
            cwd=root,
        )
    else:
        result = run(
            ["gh", "api", "--method", "POST", endpoint, "-f", f"body={body}"],
            cwd=root,
        )
    payload = json.loads(result.stdout)
    return str(payload["html_url"])
