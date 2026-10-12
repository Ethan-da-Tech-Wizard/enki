# Access Lab — portfolio case study

## The question

How might a developer and an administrator resolve a blocked-access request with a shared understanding of what needs to happen, what it costs, and whether it worked?

## Why this question

The public GitKraken Product Associate/Manager description includes shared account systems such as billing, subscriptions, organization administration, notifications, and settings. Public help articles document interactions among organizations, roles, and licenses. These sources support investigating the workflow; they do not establish the scale of the problem. Links and limitations are in `evidence.md`.

## The product decision

Build one complete journey: an invited developer requests a seat, an administrator reviews a clear cost preview, and the resulting decision updates access, saved history, and in-app messages. Support failure and retry because understanding an unsuccessful action is part of the experience.

The initial prototype uses two views and a separate reviewer control panel. The starting workspace has five occupied seats; a sixth person needs access. A second scenario has an available paid seat. The sample plan is $12 per seat per month with a fixed 15-of-30-day remaining period. This is a chosen explanatory example, not GitKraken pricing.

## How AI was directed

The supervising agent prepared a bounded brief, acceptance criteria, a source ledger, and a decision log. A separate coding agent implemented the app and tests. The supervisor independently inspected the code, ran tests, exercised browser journeys, and sent concrete corrections back to the builder. See `supervision.md` for the actual review loop.

The user's contribution at this stage is the target role, the portfolio objective, selection of the concept, and the requirement that the work be explainable and verifiable. The agents drafted scope details and implementation choices. The user has not yet personally validated those choices or run participant sessions; the case study should evolve as they review the demo.

## Decisions worth explaining in an interview

- **Scope:** one cross-system journey makes the design and outcomes inspectable in a short demo.
- **Cost clarity:** current payment and next-period cost are shown separately, alongside the sample calculation.
- **Reliable state:** one local database transaction keeps access and recorded billing outcomes consistent.
- **Safe retries:** a repeated approval uses a saved attempt result; a deliberate retry after a failure is a new attempt.
- **Fresh decisions:** if the relevant state changes while a quote is open, the administrator reviews the new preview.
- **Evidence:** implemented behavior, public source facts, demo policies, and untested product hypotheses are separately labeled.

## Observed results

See `verification.md` and the artifacts for exact technical checks. No user-performance improvements, reduced support burden, revenue gains, or conversion changes have been measured.

## Next product experiment

Have 3–5 participants attempt the workflow without coaching. Ask them to explain the cause of blocked access, what will be charged immediately, what will recur, and what to do after a failed payment. Record completion, time, mistakes, assistance, and their words. Revise the experience based on those observations and report the limits of the small sample.

## Production extension

Moving beyond the demo would require real authentication, authorization tied to authenticated identities, payment-provider reconciliation, full billing rules, external delivery for notifications if desired, a production server, and deployment/operations decisions. A real provider cannot be included in the same local SQLite transaction; that boundary needs its own design.
