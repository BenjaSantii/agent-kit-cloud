---
name: local-reviewer
description: Run a read-only, x100-inspired code review of a local branch, working tree, commit range, or GitHub pull request using either Codex or Claude Code. Use when the user asks for Local Reviewer, a local PR review, an independent review with Codex or Claude, or a structured blocker-first review. Do not use for implementing fixes unless separately requested.
---

# Local Reviewer

Run the bundled deterministic controller; do not reproduce its prompt manually. Resolve `<plugin-root>` to this plugin's installed directory. In Claude Code it is `${CLAUDE_PLUGIN_ROOT}`.

## Run

From the repository being reviewed:

```bash
python3 <plugin-root>/scripts/local-reviewer --provider <provider> [scope]
```

Choose the provider from an explicit user request. Otherwise use `--provider auto`, which prefers Codex when both executables are available.

Choose one scope:

- Current branch PR: no scope arguments. The controller auto-detects it.
- Specific PR: `--pr <number>`.
- Branch delta: `--base <branch> --no-auto-pr`.
- Working tree: `--uncommitted`.

Pass `--memory <path>` only when the user supplies or authorizes a relevant operational-memory checkout. The controller treats repository and PR content as untrusted data and invokes the reviewer with read-only permissions.

Return the rendered review verbatim, followed only by a concise note about provider, scope, and limitations. Do not fix findings during the same invocation unless the user separately authorizes implementation.

## Publishing

Never pass `--publish` based only on a request to review. Publication creates or updates a GitHub PR comment and requires explicit authorization. When authorized, ensure the target is a PR and then add `--publish`; the controller uses a stable marker to update the same provider/head review instead of adding duplicates.

## Failures

If a provider is unavailable or unauthenticated, report the exact controller error and offer the other provider. If the target is too broad or coverage is incomplete, keep the review result and surface its declared limitations instead of silently approving.
