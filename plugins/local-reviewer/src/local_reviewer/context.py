from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .errors import LocalReviewerError


@dataclass(frozen=True)
class ReviewContext:
    repository: str
    root: str
    target_kind: str
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str
    branch: str
    merge_base: str
    title: str
    description: str
    pull_request: int | None
    pull_request_url: str | None
    author: str | None
    changed_files: tuple[str, ...]
    diff_stat: str
    commit_summary: str
    memory_path: str | None

    def prompt_payload(self) -> str:
        payload = asdict(self)
        payload["changed_files"] = list(self.changed_files)
        return json.dumps(payload, ensure_ascii=False, indent=2)


def run(
    args: Sequence[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise LocalReviewerError(f"Command failed ({' '.join(args)}): {detail}")
    return result


def repository_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=candidate)
    return Path(result.stdout.strip()).resolve()


def _git(root: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd=root, check=check).stdout.strip()


def _ref_exists(root: Path, ref: str) -> bool:
    result = run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=root, check=False)
    return result.returncode == 0


def _resolve_base(root: Path, requested: str | None) -> str:
    if requested:
        candidates = [requested]
        if not requested.startswith("origin/"):
            candidates.insert(0, f"origin/{requested}")
    else:
        candidates = ["origin/test", "origin/development", "origin/main", "origin/master"]
        symbolic = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
        if symbolic:
            candidates.insert(0, symbolic.removeprefix("refs/remotes/"))
    for candidate in candidates:
        if _ref_exists(root, candidate):
            return candidate
    expected = requested or "origin/test, origin/development, origin/main, or origin/master"
    raise LocalReviewerError(f"Could not resolve a comparison branch ({expected}); pass --base explicitly.")


def _changed_files(root: Path, diff_args: Sequence[str]) -> tuple[str, ...]:
    output = _git(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", *diff_args)
    return tuple(line for line in output.splitlines() if line)


def _local_context(
    root: Path,
    *,
    base: str | None,
    head: str,
    uncommitted: bool,
    memory_path: Path | None,
) -> ReviewContext:
    head_sha = _git(root, "rev-parse", f"{head}^{{commit}}")
    branch = _git(root, "branch", "--show-current") or head
    if uncommitted:
        base_ref = head
        base_sha = head_sha
        merge_base = head_sha
        diff_args = (head,)
        title = f"Uncommitted changes on {branch}"
        target_kind = "uncommitted"
        commit_summary = _git(root, "status", "--short")
    else:
        base_ref = _resolve_base(root, base)
        base_sha = _git(root, "rev-parse", f"{base_ref}^{{commit}}")
        merge_base = _git(root, "merge-base", head_sha, base_sha)
        diff_args = (f"{merge_base}..{head_sha}",)
        title = f"{branch} → {base_ref}"
        target_kind = "branch"
        commit_summary = _git(root, "log", "--format=%h %s", f"{merge_base}..{head_sha}")
    files = _changed_files(root, diff_args)
    if uncommitted:
        untracked = tuple(
            line for line in _git(root, "ls-files", "--others", "--exclude-standard").splitlines() if line
        )
        files = tuple(dict.fromkeys((*files, *untracked)))
    if not files:
        raise LocalReviewerError("The selected target has no changed files to review.")
    return ReviewContext(
        repository=Path(root).name,
        root=str(root),
        target_kind=target_kind,
        base_ref=base_ref,
        base_sha=base_sha,
        head_ref=head,
        head_sha=head_sha,
        branch=branch,
        merge_base=merge_base,
        title=title,
        description="",
        pull_request=None,
        pull_request_url=None,
        author=None,
        changed_files=files,
        diff_stat=_git(root, "diff", "--stat", *diff_args),
        commit_summary=commit_summary,
        memory_path=str(memory_path) if memory_path else None,
    )


def _pr_context(root: Path, number: int | None, memory_path: Path | None) -> ReviewContext:
    selector = str(number) if number is not None else ""
    fields = "number,title,body,url,baseRefName,baseRefOid,headRefName,headRefOid,author,files,commits"
    args = ["gh", "pr", "view"]
    if selector:
        args.append(selector)
    args.extend(["--json", fields])
    result = run(args, cwd=root, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or "no pull request found for the current branch"
        raise LocalReviewerError(f"Could not load pull request context: {detail}")
    raw = json.loads(result.stdout)
    files = tuple(item["path"] for item in raw.get("files", []) if item.get("path"))
    if not files:
        raise LocalReviewerError("The pull request has no changed files to review.")
    base_ref = f"origin/{raw['baseRefName']}"
    base_sha = str(raw.get("baseRefOid") or "")
    head_sha = str(raw["headRefOid"])
    if not _ref_exists(root, head_sha):
        raise LocalReviewerError(
            f"Pull request head {head_sha} is not available locally; check out or fetch PR #{raw['number']} first."
        )
    if base_sha and not _ref_exists(root, base_sha):
        raise LocalReviewerError(
            f"Pull request base {base_sha} is not available locally; fetch {base_ref} first."
        )
    merge_base = _git(root, "merge-base", head_sha, base_sha) if base_sha else ""
    commit_summary = "\n".join(
        f"{item.get('oid', '')[:8]} {item.get('messageHeadline', '')}" for item in raw.get("commits", [])
    )
    stat_lines = [
        f"{item['path']} | +{item.get('additions', 0)} -{item.get('deletions', 0)}"
        for item in raw.get("files", [])
    ]
    return ReviewContext(
        repository=Path(root).name,
        root=str(root),
        target_kind="pull_request",
        base_ref=base_ref,
        base_sha=base_sha,
        head_ref=str(raw["headRefName"]),
        head_sha=head_sha,
        branch=str(raw["headRefName"]),
        merge_base=merge_base,
        title=str(raw["title"]),
        description=str(raw.get("body") or ""),
        pull_request=int(raw["number"]),
        pull_request_url=str(raw["url"]),
        author=(raw.get("author") or {}).get("login"),
        changed_files=files,
        diff_stat="\n".join(stat_lines),
        commit_summary=commit_summary,
        memory_path=str(memory_path) if memory_path else None,
    )


def collect_context(
    path: Path,
    *,
    base: str | None = None,
    head: str = "HEAD",
    pull_request: int | None = None,
    auto_pull_request: bool = True,
    uncommitted: bool = False,
    memory: Path | None = None,
) -> ReviewContext:
    root = repository_root(path)
    if uncommitted and pull_request is not None:
        raise LocalReviewerError("--uncommitted and --pr cannot be combined.")
    resolved_memory = memory or (Path(os.environ["LOCAL_REVIEWER_MEMORY"]) if os.getenv("LOCAL_REVIEWER_MEMORY") else None)
    if resolved_memory:
        resolved_memory = resolved_memory.expanduser().resolve()
        if not resolved_memory.exists():
            raise LocalReviewerError(f"Memory path does not exist: {resolved_memory}")
    if pull_request is not None:
        return _pr_context(root, pull_request, resolved_memory)
    if auto_pull_request and not uncommitted and base is None and head == "HEAD":
        try:
            return _pr_context(root, None, resolved_memory)
        except LocalReviewerError:
            pass
    return _local_context(
        root,
        base=base,
        head=head,
        uncommitted=uncommitted,
        memory_path=resolved_memory,
    )
