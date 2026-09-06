# Ultra review

Ultra mode raises assurance through independent contexts, not by asking one model to be more aggressive.

The controller performs:

1. A risk survey that partitions every Git-changed file into cohesive workstreams.
2. One fresh, read-only provider session per workstream, with tailored risks and permission to trace adjacent callers and callees.
3. A fresh adversarial verifier that reopens the code, attempts to disprove every candidate, deduplicates root causes, corrects severity, and sweeps cross-workstream boundaries.
4. Deterministic normalization that rejects citations outside the merge delta, unions attested file coverage, discloses missing coverage, and prevents approval when coverage is incomplete.

`--ultra-passes` controls the maximum number of specialist workstreams from 1 to 8; it does not include the planner and verifier. Prefer the default of 4. Use 6-8 only for changes with several independent applications or domains because runtime and provider usage grow linearly.

Ultra mode still does not execute tests or prove correctness by itself. Treat blockers as evidence-backed review candidates and declared limitations as part of the verdict. Publication remains a separate explicit `--publish` operation.
