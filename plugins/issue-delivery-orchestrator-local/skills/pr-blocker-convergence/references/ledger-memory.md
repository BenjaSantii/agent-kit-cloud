# Compact blocker memory

Read this reference only when initializing, migrating, or compacting a PR blocker memory root.

## Layout

```text
blocker-triage/
├── state.json
├── dashboard.md
├── index.jsonl
└── history/
    ├── round-01.json
    └── round-02.json
```

## `state.json`

Keep only the operational working set:

```json
{
  "schemaVersion": 1,
  "pr": 123,
  "issue": "SFW-123",
  "round": 2,
  "headSha": "abc123",
  "updatedAt": "2026-08-10T00:00:00Z",
  "counts": {"FIX": 0, "SKIP": 3, "NEEDS_USER_DECISION": 0, "STOP": 0},
  "active": [],
  "cycles": [],
  "latestEvent": "history/round-02.json"
}
```

An active blocker contains only fields required for the next action: stable ID, comment IDs/URLs, `cycleKey`, title, disposition, reason, owner, impact, failed iterations, verification plan, tool requirement, next action, and event reference. Do not copy long reviewer bodies or investigation prose into state.

## `dashboard.md`

Render a human-facing summary with:

1. PR, issue, round, SHA, checks and last update.
2. Counts and new-versus-repeated totals.
3. One concise row per active blocker.
4. Pending user decisions and `STOP` timelines.
5. Tools planned and actually used.
6. Links/paths to the latest event and external research.

Target at most 250 lines. When it grows beyond that, replace closed blocker detail with aggregate counts and event references. Do not truncate active decisions or STOP evidence.

## `index.jsonl`

Append one compact JSON object for every disposition change:

```json
{"cycleKey":"orders-null-total","commentIds":[123],"disposition":"SKIP","reason":"YAGNI","event":"history/round-01.json","at":"2026-08-10T00:00:00Z"}
```

Never load the whole index into model context. Derive a candidate `cycleKey`, then query exact IDs and keys with `rg`. When several records match, use only the latest relevant record and open its referenced event if needed.

## Round events

Store complete, immutable round evidence in `history/round-<NN>.json`: snapshot reference, blocker bodies or faithful summaries, classification evidence, corrections, validations, commits, acknowledgements, research and tool usage. A later correction appends a new event; it never rewrites an older event.

## Migration

If a legacy `<ISSUE-ID>-pr-blockers.md` exists:

1. Read it once.
2. Create compact state, dashboard and index entries.
3. Preserve the original file unchanged and record its path as `legacyLedger` in the first event.
4. Do not reread the legacy file unless a specific blocker cannot be resolved from the index and referenced events.

## Invariants

- State and dashboard are projections; history is the audit source.
- Never delete history to meet a line target.
- Never omit an active `NEEDS_USER_DECISION`, `STOP`, cycle counter or sticky disposition.
- Prefer exact retrieval over full-file reads.
