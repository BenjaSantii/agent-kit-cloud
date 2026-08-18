# Research baseline for blocker convergence

Use this reference only for uncertain classifications, unfamiliar technical claims, or cyclic repairs. Re-check the live sources when currency matters.

## Baseline principles

- Favor progress once a change improves overall code health; perfection is not the approval threshold. Source: Google Engineering Practices, “The Standard of Code Review”.
- Keep a PR focused on one self-contained change and separate large refactors. Source: Google Engineering Practices, “Small CLs”.
- When feedback is outside the PR scope, track it in another issue linked to the review rather than silently expanding the PR. Source: GitHub Docs, “Commenting on a pull request”.
- Treat iterative repair as vulnerable to patch/test overfitting. A passing narrow check is not proof that the original acceptance gap closed. Sources: “High-Quality Automated Program Repair” and “Program Repair” surveys.

## Research protocol

1. State the unresolved claim before searching.
2. Prefer repository evidence first, then official documentation, standards, and primary research.
3. Record source URL, access date, supported claim, and applicability limits in the ledger.
4. Re-evaluate the blocker; do not copy a generic recommendation into scope.
5. If research suggests a reusable workflow change, record it as a candidate and request approval after the PR loop.

## Starting sources

- https://google.github.io/eng-practices/review/reviewer/standard.html
- https://google.github.io/eng-practices/review/developer/small-cls.html
- https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/commenting-on-a-pull-request
- https://arxiv.org/abs/2104.07851
- https://arxiv.org/abs/2211.12787
