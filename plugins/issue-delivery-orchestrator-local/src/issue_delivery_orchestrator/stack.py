"""Stacked slices: a child run whose PR targets its parent slice's branch.

TurboShop squash-merges, so once a parent lands on the target its original
commits are not ancestors of the target. `restack` is therefore the only place
where this engine rewrites a branch: it rebases a stack child onto its parent
(or onto the target after the parent merged) and force-pushes with lease.
It never integrates the target into a branch that is not a stack child.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import settings
from .errors import RunBlocked
from .github import GitHubClient
from .state import save_state
from .util import run


def _git(worktree: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd=worktree, check=check).stdout.strip()


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stack_parent(state: dict[str, Any]) -> dict[str, Any] | None:
    stack = state.get("stack")
    return stack if isinstance(stack, dict) and stack.get("parentBranch") else None


def pr_target(state: dict[str, Any]) -> str:
    parent = stack_parent(state)
    if parent and not parent.get("parentMerged"):
        return str(parent["parentBranch"])
    return settings().pr_target_branch


def integration_ref(state: dict[str, Any]) -> str:
    """Remote ref the branch's own delta is measured and reviewed against."""
    return f"origin/{pr_target(state)}"


def _require_clean(worktree: Path) -> None:
    dirty = _git(worktree, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RunBlocked("Commit or discard tracked changes before rewriting stack branches")


def _is_ancestor(worktree: Path, ancestor: str, descendant: str) -> bool:
    return (
        run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=worktree,
            check=False,
        ).returncode
        == 0
    )


def _remote_sha(worktree: Path, branch: str) -> str | None:
    output = _git(worktree, "ls-remote", "--heads", "origin", branch, check=False)
    return output.split()[0] if output else None


def link_stack(
    state: dict[str, Any],
    parent_branch: str,
    *,
    parent_tip: str | None = None,
) -> dict[str, Any]:
    """Declare that this run's branch sits on top of `parent_branch`."""
    worktree = Path(state["worktree"])
    if parent_branch in {state["branch"], settings().pr_target_branch}:
        raise RunBlocked("A stack parent must be another slice branch, not the target or itself")
    _git(worktree, "fetch", "origin", parent_branch)
    tip = parent_tip or _git(worktree, "rev-parse", f"origin/{parent_branch}")
    if not _is_ancestor(worktree, tip, "HEAD"):
        raise RunBlocked(
            f"{parent_branch} tip {tip[:12]} is not an ancestor of HEAD; "
            "the branch does not sit on top of that parent"
        )
    state["stack"] = {
        "parentBranch": parent_branch,
        "parentTip": tip,
        "parentMerged": False,
        "linkedAt": _stamp(),
        "restacks": [],
    }
    save_state(state)
    return state["stack"]


def stack_cut(state: dict[str, Any], sha: str, branch: str) -> dict[str, Any]:
    """Create and push `branch` at an existing commit of this run's branch.

    Nothing is rewritten: the new branch is a lower slice made of commits the
    run already has. Link the run to the highest cut with `link_stack`.
    """
    worktree = Path(state["worktree"])
    base = integration_ref(state)
    resolved = _git(worktree, "rev-parse", "--verify", f"{sha}^{{commit}}")
    if resolved == _git(worktree, "rev-parse", "HEAD"):
        raise RunBlocked("Cut below HEAD; the top slice stays on this run's branch")
    if not _is_ancestor(worktree, resolved, "HEAD") or _is_ancestor(worktree, resolved, base):
        raise RunBlocked(f"{sha} is not a commit of this branch above {base}")
    if _git(worktree, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
        raise RunBlocked(f"Branch {branch} already exists locally")
    if _remote_sha(worktree, branch):
        raise RunBlocked(f"Branch {branch} already exists on origin")
    _git(worktree, "branch", branch, resolved)
    _git(worktree, "push", "-u", "origin", f"{branch}:{branch}")
    cuts = state.setdefault("stackCuts", [])
    cuts.append({"branch": branch, "sha": resolved, "createdAt": _stamp()})
    save_state(state)
    return cuts[-1]


def slice_extract(
    state: dict[str, Any],
    commits: list[str],
    branch: str,
) -> dict[str, Any]:
    """Move independent commits to a new branch based on the target.

    Allowed only before this run's branch is pushed: the run's own branch is
    rebuilt without those commits, and its previous HEAD is recorded.
    """
    worktree = Path(state["worktree"])
    _require_clean(worktree)
    if state.get("pr") or _remote_sha(worktree, state["branch"]):
        raise RunBlocked(
            "Extracting commits rewrites this branch; only allowed before it is pushed. "
            "Use stack_cut for a pushed branch"
        )
    if stack_parent(state):
        raise RunBlocked("Extract independent slices from a run that is not a stack child")
    target = settings().pr_target_branch
    _git(worktree, "fetch", "origin", target)
    base = _git(worktree, "merge-base", "HEAD", f"origin/{target}")
    ordered = _git(worktree, "rev-list", "--reverse", f"{base}..HEAD").split()
    wanted = {_git(worktree, "rev-parse", "--verify", f"{item}^{{commit}}") for item in commits}
    unknown = wanted - set(ordered)
    if not wanted or unknown:
        raise RunBlocked(f"Commits not on this branch above the target: {sorted(unknown)}")
    if any(len(_git(worktree, "rev-list", "--parents", "-n", "1", sha).split()) > 2 for sha in ordered):
        raise RunBlocked("The branch contains merge commits; extract manually")
    previous_head = _git(worktree, "rev-parse", "HEAD")
    original = state["branch"]

    def replay(new_branch: str, start: str, picks: list[str]) -> None:
        _git(worktree, "switch", "-q", "-c", new_branch, start)
        for sha in picks:
            result = run(["git", "cherry-pick", sha], cwd=worktree, check=False)
            if result.returncode != 0:
                run(["git", "cherry-pick", "--abort"], cwd=worktree, check=False)
                _git(worktree, "switch", "-q", "--force", original)
                _git(worktree, "branch", "-D", new_branch, check=False)
                raise RunBlocked(
                    f"Commit {sha[:12]} does not apply independently on {start[:12]}; "
                    "the slices are not independent. Keep one PR or cut a stack instead"
                )

    replay(branch, f"origin/{target}", [sha for sha in ordered if sha in wanted])
    _git(worktree, "switch", "-q", original)
    remaining = [sha for sha in ordered if sha not in wanted]
    scratch = f"{original}-slice-rebuild"
    replay(scratch, base, remaining)
    rebuilt = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "switch", "-q", original)
    _git(worktree, "reset", "-q", "--hard", rebuilt)
    _git(worktree, "branch", "-D", scratch)
    _git(worktree, "push", "-u", "origin", f"{branch}:{branch}")
    record = {
        "branch": branch,
        "commits": [sha for sha in ordered if sha in wanted],
        "previousHead": previous_head,
        "rebuiltHead": rebuilt,
        "extractedAt": _stamp(),
    }
    state.setdefault("sliceExtractions", []).append(record)
    save_state(state)
    return record


def _parent_pull_request(github: GitHubClient, parent_branch: str) -> dict[str, Any] | None:
    output = run(
        [
            "gh", "pr", "list", "--head", parent_branch, "--state", "all",
            "--json", "number,url,state,mergedAt,baseRefName",
        ],
        cwd=github.cwd,
    ).stdout
    items = json.loads(output or "[]")
    merged = next((item for item in items if item.get("mergedAt")), None)
    return merged or next((item for item in items if item.get("state") == "OPEN"), None)


def require_parent_pr(state: dict[str, Any], github: GitHubClient) -> None:
    """A stack child's PR needs its parent's PR to exist first (open or merged)."""
    parent = stack_parent(state)
    if not parent or parent.get("parentMerged"):
        return
    if not _parent_pull_request(github, str(parent["parentBranch"])):
        raise RunBlocked(
            f"Open the PR of parent slice {parent['parentBranch']} before this child's PR"
        )


def restack(state: dict[str, Any], github: GitHubClient) -> dict[str, Any]:
    parent = stack_parent(state)
    if not parent:
        raise RunBlocked("This run is not a stack child; restack only applies to stacks")
    worktree = Path(state["worktree"])
    _require_clean(worktree)
    target = settings().pr_target_branch
    parent_branch = str(parent["parentBranch"])
    _git(worktree, "fetch", "origin", target)
    parent_pr = _parent_pull_request(github, parent_branch)
    merged = bool(parent_pr and parent_pr.get("mergedAt"))
    if merged:
        onto = f"origin/{target}"
    else:
        if not _remote_sha(worktree, parent_branch):
            raise RunBlocked(f"Parent branch {parent_branch} no longer exists on origin")
        _git(worktree, "fetch", "origin", parent_branch)
        onto = f"origin/{parent_branch}"
    onto_sha = _git(worktree, "rev-parse", onto)
    old_tip = str(parent["parentTip"])
    previous_head = _git(worktree, "rev-parse", "HEAD")
    if not merged and onto_sha == old_tip:
        return {"restacked": False, "reason": "parent unchanged", "stack": parent}

    result = run(
        ["git", "rebase", "--onto", onto_sha, old_tip],
        cwd=worktree,
        check=False,
    )
    if result.returncode != 0:
        run(["git", "rebase", "--abort"], cwd=worktree, check=False)
        raise RunBlocked(
            f"Restack onto {onto} conflicts; the branch was left at {previous_head[:12]}. "
            "Resolve with the user before retrying"
        )
    new_head = _git(worktree, "rev-parse", "HEAD")
    remote_before = _remote_sha(worktree, state["branch"])
    if remote_before:
        _git(
            worktree,
            "push",
            f"--force-with-lease={state['branch']}:{remote_before}",
            "origin",
            f"HEAD:{state['branch']}",
        )
    retargeted = None
    if merged and state.get("pr"):
        run(["gh", "pr", "edit", state["pr"]["url"], "--base", target], cwd=worktree)
        retargeted = target
        state["pr"]["base"] = target
    parent.update(
        {
            "parentTip": onto_sha,
            "parentMerged": merged,
        }
    )
    parent.setdefault("restacks", []).append(
        {
            "onto": onto,
            "ontoSha": onto_sha,
            "previousTip": old_tip,
            "previousHead": previous_head,
            "newHead": new_head,
            "forcePushed": bool(remote_before),
            "retargetedTo": retargeted,
            "restackedAt": _stamp(),
        }
    )
    save_state(state)
    return {"restacked": True, "stack": parent}
