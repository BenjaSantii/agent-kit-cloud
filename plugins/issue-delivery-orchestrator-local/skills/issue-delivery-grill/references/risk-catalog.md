# Risk catalog

Six categories that caused most blockers reaching PR review across 30 TurboShop PRs (about 190
distinct root causes). Each category lists the questions to put to the code, the signals that mean
`Yes`, a real example, and the usual lowest seam that falsifies it.

A `No` needs repository evidence: the path, symbol or `rg` command showing the risk cannot occur.
A `Yes` needs a `Testing Decisions` row and, where noted, a subsection.

## `concurrency`

Two actors, requests or retries touching the same state.

Ask the code:

- Is anything read, decided on, then written, with an external call or user wait in between
  (check-then-act)? What if it changes in that gap?
- Can the same command arrive twice (lost response, double click, offline replay)? Is there an
  idempotency key, and is it checked before any new validation?
- Can an older response arrive after a newer one or after a local action (polling, refetch,
  rehydration)? What invalidates it?
- Does a token refresh, rotation or version bump race with logout, revoke or save?

`Yes` signals: `save` of a previously loaded entity, optimistic versions, polling hooks, offline
queues, refresh tokens, multi-step approvals.

Examples: approval evaluated before the lock let a new stop through (LOG-323). Cancel overwrote a
meeting that was scheduled in between (LOG-298). A delivered order reappeared from an in-flight
poll (LOG-265). Logout raced a refresh and left a live session (LOG-269).

Seam: an interleaving test with deferred promises (client) or two transactions on real Postgres
(server). Requires `### State model`.

## `external-failure`

Any dependency that can fail, time out or answer late: ERP, Google, push, BFF, printers, network.

Ask the code:

- For each external call: what happens on failure, on timeout, on a lost response where the
  server did succeed, and with stale cached data?
- Is "unknown" distinguishable from "failed" and from "empty" all the way to the UI?
- Do client and server timeouts agree? Do global filters or serializers strip the error code the
  client branches on?

`Yes` signals: any new or changed remote call, retries, caches, fallbacks, `503`, offline mode.

Examples: a write timeout treated as "not saved" while the ERP had saved it, spread over seven
review rounds (LOG-255). A route failure fell back to a direct ETA and showed `OPEN` (LOG-323). A
failed prepare opened printing anyway (LOG-325).

Seam: fault-injection unit tests for fail, timeout, lost response and stale cache, plus one HTTP
test through the global filter. Requires `### State model` with the unknown-outcome state.

## `async-lifecycle`

Work that outlives the component, screen or session that started it.

Ask the code:

- After each `await`, can the owner be unmounted, blocked, logged out or superseded? Does the
  continuation still open prompts, register listeners, start audio or tracking, or write state?
- Is there one cancellation mechanism (AbortSignal or generation token) that reaches the services,
  not only the hook?
- Are native dialogs, modals or alarms owned by something that reacts to the block or unmount?

`Yes` signals: permission flows, background tracking, push registration, alarms, native `Alert`,
global blocking screens, focus or foreground effects.

Examples: fifteen consecutive rounds each finding one more continuation that escaped the
location block (LOG-272). An alarm kept ringing under the blocking screen (LOG-248).

Seam: tests that unmount or block while a promise is pending, then resolve it late. Design one
cancellation pattern in the spec instead of patching each `await`.

## `edge-cases`

Boundaries of time, size and population.

Ask the code:

- Time: exact boundaries (inclusive or exclusive), DST in America/Santiago, midnight, Friday to
  Monday, historical cut-over dates, the current date leaking into a pure conversion.
- Size: first page of N, groups larger than a page or label, zero, one and many.
- Population: denominators, excluded records, negative durations, mixed policies in one aggregate.
- Input: coercion that turns invalid input into a different valid value, route variants such as a
  trailing slash, `HEAD` or casing.

Examples: `toTime` shifting an hour on DST (LOG-334). Labels overflowing with large reference
groups (LOG-325). SLA at 200% after a denominator change (LOG-299). `HEAD` bypassing a guard
(LOG-248).

Seam: table-driven unit tests with fake timers pinned to the trap dates.

## `consumers-platforms`

Everything that reads what the change modifies.

Ask the code:

- `rg` every changed field, enum, rule and endpoint. Who reads it: web, Android, iOS, PDF, HTML,
  email, reports, maps, inbox, case files, other services?
- Does shared code change behavior on a platform that is out of scope (iOS when targeting
  Android)?
- Do two renderings of the same data (HTML and PDF, card and marker) compute it separately?

Examples: the new SLA rule missed the inbox, map markers, the case file and the driver detail
over six review rounds (LOG-324). HTML and PDF grouped incidents differently (LOG-299). A shared
precondition broke iOS drivers (LOG-272).

Seam: a parity test feeding one DTO to every renderer, plus the inventory as the checklist.
Requires `### Consumer inventory`.

## `roles-authorization`

Who may do it, and whether the check uses current state.

Ask the code:

- Which roles hit each new or changed endpoint and screen? Does every role in the matrix behave?
- Is authorization based on the current assignment or ownership, or on a historical event?
- Does a guard or validator run in an order that consumes rate limits or changes the error?

Examples: authorization from a historical assignment event let an unassigned packer edit
(LOG-325). Field Managers got 403 on a device-token call during logout (LOG-269). Real pickup
assignments used `COLLECTOR`, not `DRIVER` (LOG-272).

Seam: a role-matrix test per endpoint.
