# Builder supervision record

## Assignment 1 — initial implementation

The root agent prepared the scope in `brief.md`, source boundaries in `evidence.md`, and decisions in `decisions.md`. A separate coding agent will implement the runtime, meaningful tests, and run instructions in the shared workspace.

Review loop: assign bounded work → inspect artifacts → independently exercise the behavior → record observed defects → prompt the builder to correct them → rerun affected checks. Agent claims alone do not count as verification.

The root agent owns this record and the final verification report. The builder owns implementation files and its unit/integration tests. Any edits outside those areas are coordinated.

### Architecture checkpoint

Builder proposed a local Python HTTP server, SQLite, and a static browser UI. Approval writes will be transactional and require a server-generated quote fingerprint and an idempotency key. The root accepted this approach and required checks for stale quotes, concurrent retries, failed-payment replay, and conflicting reuse of a key.

The root clarified that selectable demo identities are not authentication, that unknown identities must fail, that permissions must depend on server-side membership, and that developer responses must not expose other users' private requests or messages. The root also required loopback binding and rejection of cross-origin mutations. Independent verification scripts will live under `verification/`.

## Independent review 1

Builder delivered the server, UI, tests, and README and reported 23 passing tests. The supervisor independently reran the 23 tests, inspected the domain/API/UI code, and exercised complete desktop/mobile browser journeys. The supervisor's separate API verifier then passed 14 checks, including real server process restart and eight concurrent requests for each approval-key scenario.

Observed UI issues sent back as Assignment 2:

- Explanatory copy was small and faint; measured example contrasts ranged from 2.58:1 to 3.32:1 on their backgrounds.
- A failed request could retain the transient “Sending request…” button label.
- Compressed stylesheet formatting made manual review difficult.
- The evidence panel needed a link to the verification report.

The root asked the builder to correct these issues without changing stable business rules, then rerun affected checks. The builder accepted the follow-up. Browser setup required permission to run Chromium outside the sandbox; the independent API test required permission to create local server sockets. Both scoped commands were approved.

## Independent review 2 and completion

The builder increased essential copy/control sizes, darkened secondary text, formatted the stylesheet, restored failed-action labels, and added the verification link. Domain/API files were unchanged. A supervisor check then measured one remaining status paragraph at 4.4715:1 because of reduced opacity. The supervisor sent a targeted correction; the builder removed that opacity and returned stable files.

The final supervisor browser run passed 12 check groups, including the corrected button behavior and a deliberately lost approval response. Essential copy sampled by the verifier was 13px or larger with contrast at least 5.0259:1. Two injected connection resets were handled; there were no unexpected browser errors. The separate API verification passed 14 checks and the previously rerun builder suite passed 23 tests.

The builder stopped its temporary test server. The supervisor left the review demo reset to Maya's starting scenario. The code, test scripts, sources, decisions, walkthrough, case study, screenshots, and verification report are the completed local handoff. Public deployment and human usability validation have not been performed.
