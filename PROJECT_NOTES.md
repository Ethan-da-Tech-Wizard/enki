# Access Lab

An independent local portfolio prototype: a developer requests a team seat, an administrator reviews the cost, and access, billing, and in-app notifications move together.

This is not a GitKraken product or integration. All people, organizations, prices, billing periods, and payment results are fictional demo data. The product hypothesis has not been validated with users.

## Run

Requires Python 3.11 or newer. No package installation, build step, fonts, remote assets, or runtime network services are needed.

```sh
python3 -m app.server
```

Open **http://127.0.0.1:8765**. Stop with Ctrl+C. The first run creates `data/access-lab.sqlite3`; subsequent runs keep its saved state. The server accepts only loopback connections.

For a separate disposable demo database or a different port:

```sh
python3 -m app.server --port 8766 --db /tmp/access-lab-review.sqlite3
```

`--host` may be a loopback address such as `127.0.0.1`, `localhost`, or `::1`. A public bind is rejected. Do not reverse proxy or publish this application.

## Try the complete journey

1. Start as **Maya**, the invited developer in Northstar Studio. Five of five paid seats are assigned. Choose **Request access**.
2. Open **Demo controls & evidence** and choose **Eli**, the administrator. Choose **Review request**.
3. Review the sample arithmetic: **$12 × 15 / 30 days = $6 now**, then **6 × $12 = $72** next period. Approve the simulated purchase.
4. Switch back to Maya. **Open workspace** now retrieves a small server-gated fictional workspace preview. Read the in-app notification and activity record.

To demonstrate recovery, reset the sample data using the separate demo controls, send a request, and set the simulated payment result to **Failure** before approval. No successful charge or additional seat is created. Set the result back to **Success**, then **Review & retry**. To show a free assignment, reset to **One available paid seat**: approval costs $0 and creates no payment attempt.

Reset clears only the configured demo database’s sample records, including both sample organizations, and restores the simulated payment result to success. The reset checkbox makes that explicit. Juniper Labs identities provide a second organization for inspecting isolation.

## Verification

Run the builder’s integration, concurrency, permission, and HTTP tests against temporary databases:

```sh
python3 -m unittest discover -s tests -v
```

The tests cover duplicate requests, sample price calculation, atomic rollback, payment failure and recovery, successful/failed attempt replay, payload mismatch, same-key and different-key concurrency, stale quotes, spare seats, state reopening, request denial, organization isolation, server access gating, input validation, Origin/Host protection, and loopback binding. They do not measure human usability or business impact. The supervising agent records its separate review in `docs/` and any additional checks in `verification/`.

## How it works

| Piece | Responsibility |
| --- | --- |
| `app/domain.py` | SQLite schema, sample policy, permissions, quotes, and business transitions. |
| `app/server.py` | Standard-library threaded HTTP server, JSON validation, local origin checks, and static/evidence files. |
| `app/static/` | Plain HTML/CSS/JavaScript. Developer/admin perspectives, cost review, notifications, activity, and separate demo controls. |
| `tests/` | Builder-owned executable checks using Python’s standard library. |
| `docs/` | Supervisor-owned scope, public evidence, assumptions, decisions, and review record. |

Amounts are integer cents. SQLite `BEGIN IMMEDIATE` serializes writes. A successful approval saves the simulated charge, added seat if needed, assignment, membership change, request outcome, notifications, activity, and attempt result in one transaction. A failure saves a failed payment attempt and recovery state without adding a seat or assignment. A real payment provider would require a different distributed transaction/reconciliation design.

Cost previews are generated from current server state. A quote fingerprint includes the scenario epoch, organization revision, seat/assignment counts, and request state. Changed state requires a fresh review. The client cannot supply a price or target user for a new request.

Each approval carries an attempt key. Retrying the same key with the same payload returns the stored success or failure; reusing it for another payload returns a conflict. A deliberate retry after a failed payment uses a fresh quote and key. Concurrent different-key approvals of a resolved request cannot purchase another seat. The browser preserves the same key after a lost response while its review dialog remains open; persisted request state prevents a second purchase even after a refresh.

Access depends on both organization membership and an assigned seat. The request’s `approved` label alone does not grant access. Notifications are persisted in-app messages. Events are append-only through the business API; deliberate demo reset clears the sample history.

## Local JSON interface

Product requests require `X-Demo-User: maya`, `eli`, `quinn`, or `robin` (additional seeded teammates also exist). This header selects a **demo persona**, not authenticated identity. Missing/unknown identities fail; product routes enforce the selected persona’s role and organization.

| Route | Behavior |
| --- | --- |
| `GET /api/workspace` | Current persona’s workspace, permitted requests/activity, own notifications; admins also see their organization’s team and payments. |
| `GET /api/shared-workspace` | Small fictional workspace preview; requires membership and an assigned license. |
| `POST /api/requests` with `{}` | Self-request; repeated active requests return the original record. |
| `GET /api/requests/{id}` | Own request or an admin’s organization request. |
| `GET /api/requests/{id}/quote` | Admin-only current cost preview; self-approval is forbidden. |
| `POST /api/requests/{id}/approve` | Body: `quote_token`, `idempotency_key`. Admin-only transition. |
| `POST /api/requests/{id}/deny` with `{}` | Admin-only, replay-safe denial; the developer may later request again. |
| `POST /api/notifications/read` with `{}` | Mark only the selected persona’s notifications as read. |
| `GET /api/demo/info` | Reviewer controls: fictional persona names, current scenario/payment result. |
| `POST /api/demo/payment` | Reviewer control body: `result: "success"` or `"failure"`. |
| `POST /api/demo/reset` | Reviewer control body: `scenario: "full"` or `"spare"`, plus `confirm: "RESET DEMO"`. |

POST bodies must be JSON objects with `Content-Type: application/json`. Unknown fields are rejected. Requests with a foreign Origin, nonlocal Host, wrong port, or cross-site fetch marker are rejected. Demo controls deliberately operate outside product persona permissions so a reviewer can explore both sides; they are not subscription administration endpoints and do not provide production security.

## Evidence and boundaries

- [Product brief and acceptance criteria](docs/brief.md)
- [Public sources, invented policies, and unknowns](docs/evidence.md)
- [Decision log](docs/decisions.md)
- [Builder supervision record](docs/supervision.md)
- [Independent verification report](docs/verification.md)
- [Portfolio case study](docs/case-study.md)
- [Two-minute walkthrough](docs/walkthrough.md)

The UI links directly to these read-only documents. The supervisor owns independent verification; builder test results alone are not a product endorsement.

This prototype does **not** implement production login, payment processing, tax rules, actual email, repositories/code review, SSO, a GitKraken connection, or a public deployment. The fixed 30-day period and 15 remaining days are explanatory sample rules, not a calendar or a claim about GitKraken’s prices. The preview illustrates successful access; it is not a code-review application. A production version would need authenticated identities, provider reconciliation, deployment/security review, full billing policy, and retention/observability decisions.

No participant sessions have been performed. Screenshots, passing tests, and simulated outcomes demonstrate implemented behavior, not a measured improvement in support, conversion, or retention.
