# Access Lab — product brief

Status: working scope based on the user's accepted concept, 2026-10-01. Detailed demo policies below are choices made by the supervising agent.

## Purpose

Create a small, working portfolio system demonstrating how a product manager coordinates permissions, subscriptions, billing, notifications, and recovery. A separate AI builder implements it under the root agent's review. Every significant choice should have a reason and a way to check it.

## Audience and hypothesis

- Developer: understand why a paid collaboration feature is unavailable and request access.
- Administrator: approve the right request with a clear view of price and access changes.
- Portfolio reviewer: understand and verify the workflow in about two minutes.

Hypothesis: putting an access explanation and an appropriate next action together helps people resolve access problems with less assistance. This has not been tested with users. Do not invent success rates, customer quotes, support savings, or conversion improvements.

## First complete journey

1. The sample organization, Northstar Studio, has five paid seats, all occupied. Maya, a sixth invited developer, has no seat. Eli is the administrator and already occupies one of the five seats.
2. Maya sees an accurate explanation and requests access to the shared review workspace.
3. Eli sees the pending request and a transparent cost preview.
4. Eli approves with a simulated payment. On success, the organization has six paid seats and six assignments; Maya gets access. Both views show the outcome and a relevant in-app notification.
5. Simulated payment failure leaves the request recoverable, grants no access, creates no successful charge, and allows a deliberate retry.
6. A replay of a successful approval must return the original result without another purchase or notification.

## Demo policies (invented, not GitKraken prices or exact internal behavior)

- One monthly sample plan at $12 per seat. Fixed demonstration billing period: 30 days, 15 remaining. A new seat costs $6 immediately; next period for six seats costs $72. Show the calculation and label sample pricing and simulated charges wherever relevant.
- A pending invitation does not consume a seat until approval. This is our simplified demo policy.
- An available paid seat can be assigned with $0 additional charge. Approval must use current server state, never a client-supplied total.
- Only the administrator of the relevant organization can approve or deny; developers can request for themselves and see only their own requests/notifications. Admins cannot approve their own request.
- Request states include pending, payment_failed, approved, denied. Access derives from membership and assigned license, not just the request label.
- A reviewer can reset sample scenarios and choose a demo persona. This is a demonstration identity system, not real authentication. Default bind is 127.0.0.1.
- Demo notifications are persisted in-app messages, not emails. History is an append-only product activity timeline except when deliberately resetting the demo.

## Scope

- Polished, responsive developer and administrator views with a clear visual hierarchy, keyboard access, readable contrast, loading/error/success states, and helpful next actions.
- Separate compact demo controls: switch persona, reset scenario (full seats; available seat), choose payment result, inspect explanatory evidence. Do not put implementation details in normal user messages.
- Persisted requests, seat assignments, simulated transactions, notifications, and event history in SQLite.
- Server permission enforcement and input validation, including isolation between organizations if a second org is seeded for tests.
- A guided two-minute demo or walkthrough and a concise explanation of the source assumptions.
- Read-only evidence documentation accessible from the app or a clearly linked case-study page. No remote fonts/images needed; use CSS and inline SVG where useful.

## Acceptance criteria

| ID | Expected behavior | Verification |
| --- | --- | --- |
| AC-01 | A developer sees the seat shortage and can create one access request; repeated clicks do not duplicate it. | API test and browser journey |
| AC-02 | A developer cannot approve requests, modify subscriptions, or read another person's private requests through the API. | Unauthorized API requests |
| AC-03 | Admin sees $6 now / $72 next period for the seeded full-seat case, with sample pricing and arithmetic. | Backend assertions and browser preview |
| AC-04 | Successful approval atomically creates one charge, one added seat, one assignment, approved status, notifications, and activity. | Integration test and persisted state check |
| AC-05 | Payment failure preserves request and seat counts; UI explains recovery; a new deliberate retry can succeed. | Integration test and browser journey |
| AC-06 | Repeated or concurrent approvals cannot create duplicate purchases or assignments. | Replay and concurrent API test |
| AC-07 | Existing spare seat is assigned without a new purchase; stale previews require review when cost/state changes. | Integration/API tests |
| AC-08 | Normal state survives server restart; reset affects only the demo database and is labeled. | Restart and reset checks |
| AC-09 | Mobile and desktop flows work with no page errors or clipped primary actions. | Browser checks and screenshots |
| AC-10 | App and documents distinguish public sources, demo assumptions, measured checks, and unvalidated hypotheses. | Supervisor review |

## Boundaries for the first version

Local demonstration only. Production login, payment processing, email delivery, SSO, exact tax/proration rules, live GitKraken integration, and public deployment are future work. Code and evidence should make these boundaries easy to explain. Do not add an LLM to make billing or permission decisions.

## Completion

Root agent verifies acceptance criteria independently, sends concrete defects back to the builder, and repeats until required behavior works. Leave a runnable local app, repeatable tests, evidence/decision/review logs, and an honest final verification report. Human usability results and external business impact remain unvalidated until real sessions happen.
