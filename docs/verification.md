# Verification report

Status: first local prototype verified; required implementation and review corrections complete. Updated 2026-10-01.

## What is verified

- Supervisor reran all 23 builder-owned tests successfully.
- Supervisor wrote and ran 14 black-box checks against separate local server processes. These cover role/organization boundaries, sample price arithmetic, rejected client prices, failed payment replay, successful recovery, notification privacy, real process restart, eight concurrent same-key approvals, eight concurrent different-key approvals, zero-cost assignment, stale quotes after reset, denial/re-request, malformed input, and loopback binding.
- Final Playwright run passed 12 scenario/check groups: desktop and 390px mobile journeys, payment failure/recovery, zero-cost assignment, notifications, evidence links, selected essential-text readability, interrupted-request recovery, and lost-approval-response replay. The browser was Chromium 153.0.8010.52.
- The final browser run had zero unexpected console/page errors. Two connection-reset errors were deliberately injected and correctly handled. A lost approval response was retried with the identical attempt payload and left exactly one purchase.
- Selected essential explanatory text in the tested developer and cost-review views measured at least 13 CSS pixels and a minimum computed contrast ratio of 5.0259:1. This is a targeted measurement, not a complete accessibility audit.

The API verifier asserts resulting state as well as response codes. Concurrent approval checks confirmed exactly one successful purchase, one assigned seat, and one access-granted event/notification. Restart checks stopped one server process and started a new process with the same database, then compared persisted responses.

## Review findings and corrections

1. Some explanatory copy used very small type and insufficient contrast. For example, `#849087` on white measured 3.32:1. The builder increased type sizes and darkened text. A follow-up check found that reduced opacity left one amber paragraph at 4.4715:1; the builder removed the opacity and the final computed checks passed.
2. A request interrupted by a network failure could leave a clickable button labeled “Sending request…”. The builder restored the original action label on failure; an independently injected network error verified the correction and subsequent retry.
3. The stylesheet had long compressed lines. It is now formatted into readable rules.
4. The evidence panel now links directly to this report.

An initial browser test also checked a quote before it finished loading. The supervisor corrected the test to wait for the approval control; this was a verifier timing issue, not an application defect.

## Reproduce

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 verification/verify_api.py
```

For browser checks, run a dedicated app instance with a disposable demo database, then run `verification/browser.mjs`. See `verification/README.md` for setup. Browser checks reset sample data on the selected local server.

Machine-readable results and screenshots are under `verification/artifacts/`. Passing scripts exit with code 0; a failed assertion returns a nonzero exit code and records the failure. `initial-quote-check.png` preserves the earlier verifier timing observation; `ready-to-review.png` is the final clean entry screen.

## Acceptance trace

| Brief criterion | Evidence |
| --- | --- |
| AC-01 — explanation and duplicate request handling | Browser request journey; independent repeated-request check; builder concurrent-request test. |
| AC-02 — role and private-data boundaries | Independent role/organization checks and builder API tests. Demo identity selection remains deliberately open. |
| AC-03 — clear, accurate sample prices | Independent integer-cent arithmetic check and desktop/mobile cost previews. |
| AC-04 — consistent approval state | Independent charge/seat/assignment/access/event checks; builder rollback test. |
| AC-05 — failure and deliberate retry | API and browser failure/recovery journeys. |
| AC-06 — replay and concurrency | Eight same-key and eight different-key simultaneous HTTP approvals; browser lost-response retry. |
| AC-07 — spare seats and stale previews | Independent zero-cost and stale-quote checks; builder state-change test. |
| AC-08 — persistence and reset | Independent server-process restart, reset invalidation, and browser reset controls. |
| AC-09 — desktop/mobile usability of controls | Completed browser journeys at 1440px and 390px, overflow checks, screenshots, and a targeted keyboard/contrast check. |
| AC-10 — evidence boundaries | Supervisor review of UI, README, brief, sources, decisions, and case study. |

## Limits of these claims

This is a local demonstration with selectable identities and simulated payments. Tests establish implemented behavior under the scenarios exercised. They do not establish production readiness, full accessibility compliance, compatibility with every browser, real payment-provider behavior, or customer/business impact. No usability sessions have been conducted. No claim is made that the hiring role is currently available.
