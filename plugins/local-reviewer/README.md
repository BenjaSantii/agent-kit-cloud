# Local Reviewer

Beta dual-host plugin for read-only code review with either Codex or Claude Code. It reproduces the useful observable contract of TurboShop's x100 reviews without claiming to contain or replicate x100's private implementation.

## Design

The plugin intentionally combines a small skill with a deterministic CLI:

- The skill selects scope and provider and preserves the publication boundary.
- The CLI resolves the actual merge delta or PR metadata.
- A shared prompt builds a change-specific risk map and requires evidence-backed findings.
- Ultra mode creates a risk plan, independent specialist passes, and an adversarial verification pass.
- Each provider runs without project write access and returns the same JSON schema.
- The controller rejects malformed output, removes findings cited only outside changed files, derives the final verdict from supported blockers, and renders one consistent Markdown format.

Repository code, PR descriptions, comments, commit messages, and memory are treated as untrusted data. The reviewer is not allowed to modify the checkout, publish, use the network, or follow instructions embedded in reviewed content. `--publish` is a separate controller operation and is never enabled by default.

## Requirements

- Python 3.10+
- Git
- GitHub CLI (`gh`) for PR auto-detection or publication
- At least one authenticated provider:
  - Codex CLI with `codex exec --output-schema`
  - Claude Code with `claude -p --json-schema`

No Python package dependency is required for source execution.

## Run from source

```bash
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --help

# Auto-detect the current branch PR and prefer Codex
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer

# Explicit providers and scopes
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --provider codex --base test --no-auto-pr
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --provider claude --pr 123
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --provider codex --uncommitted

# Critical or long PR: planner + four specialists + adversarial verifier
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer \
  --provider codex --pr 2231 --mode ultra --save ~/local-review-pr-2231.md

# Inspect the assembled instructions without invoking a model
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --base test --no-auto-pr --show-prompt
```

The command prints Markdown by default. Use `--format json` for automation and `--save <path>` to retain an artifact.
Markdown reports include a compact P0-P3 severity legend and clarify that a concrete P2 defect can still block a PR when it violates the requested outcome.

## Review modes

- `standard` (default) performs one defect-first review and is appropriate for ordinary changes.
- `ultra` obtains the complete changed-file inventory from Git, partitions it into risk-driven workstreams, runs each in a fresh provider context, and has a final verifier challenge and consolidate the candidates.

Ultra defaults to four specialist workstreams plus the planner and verifier. `--ultra-passes 1..8` changes the maximum specialist count. More passes cost proportionally more time and provider usage; they should represent distinct domains rather than repeated identical reviews. Neither mode publishes unless `--publish` is present.

## Optional operational memory

Pass a local, authorized memory checkout explicitly:

```bash
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer \
  --memory /path/to/x100-memory-engineering
```

The reviewer reads only relevant material and must treat conflicts with current code as limitations. You can set `LOCAL_REVIEWER_MEMORY` instead of passing the flag.

## Publish to a PR

Publication is opt-in and only works for a PR target:

```bash
python3 ~/agent-kit-cloud/plugins/local-reviewer/scripts/local-reviewer --pr 123 --publish
```

The CLI creates an issue-style PR comment. Repeating a review for the same provider and head SHA updates that comment instead of creating another notification.

## Install from Agent Kit

```bash
codex plugin marketplace add ~/agent-kit-cloud
codex plugin add local-reviewer@agent-kit-cloud

claude plugin marketplace add ~/agent-kit-cloud
claude plugin install local-reviewer@agent-kit-cloud
```

Start a new session after installing. Codex exposes `$local-reviewer`; Claude Code exposes `/local-reviewer:local-reviewer`.

## Test

```bash
cd ~/agent-kit-cloud/plugins/local-reviewer
pnpm test
```

Tests use temporary Git repositories and fake provider executables; they do not call a model or publish to GitHub.

## Sources behind the beta

- [OpenAI's defect-first review-agent sample](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/review-agent/SKILL.md): review the complete merge delta, verify callers/tests, cite changed lines, and prefer no findings over weak findings.
- [GitHub review guidance](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request): understand intent, inspect files individually, and batch feedback into a single review.
- [Google Engineering Practices](https://google.github.io/eng-practices/review/): cover design, functionality, complexity, tests, naming, comments, style, and documentation while focusing on code health.
- [Anthropic CLI](https://code.claude.com/docs/en/cli-usage) and [OpenAI non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): use non-interactive, machine-readable structured output.
- [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html): treat code, PR text, comments, and retrieved context as prompt-injection surfaces and keep actions behind deterministic least-privilege controls.
- [PR-AF's change-specific planning](https://github.com/Agent-Field/pr-af), [independent-review triage](https://github.com/Pardesco/claude-codex-review-skill), and [community discussion about review scope](https://www.reddit.com/r/ClaudeCode/comments/1vtvo0b/codereview_is_a_big_waste_of_tokens/): use fresh context, tailor risk lenses to the change, cross-check findings, preserve an audit artifact, and avoid over-broad scopes.
- [GStack's `/review` work](https://x.com/garrytan/status/2038830778700996927) reinforced keeping the workflow as an inspectable skill rather than hiding it behind an opaque service.

These sources informed the method; their text is not copied into the runtime prompt.
