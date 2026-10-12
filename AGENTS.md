# Access Lab

Independent local portfolio prototype for the GitKraken Product Associate/Manager role.

- Read `docs/brief.md`, `docs/evidence.md`, and `docs/decisions.md` before implementation.
- The user asked for a supervisor to direct a separate builder AI and check its work. The root agent owns scope, independent verification, and the evidence trail. The builder owns implementation and its tests. Coordinate edits; do not overwrite another agent's work.
- Keep documented GitKraken behavior separate from our invented demo policies. Sample prices, people, organizations, transactions, and measurements must be labeled honestly.
- Runtime: Python 3.11+ standard library, SQLite, plain HTML/CSS/JavaScript. No build step or remote runtime dependencies. Explain additions before using them.
- Persist state and enforce business rules on the server. Use integer cents for money. Use transactions for purchase/access changes and make retries safe.
- This is a loopback-only demonstration with selectable demo identities and simulated payments. Do not claim production authentication, real payment integration, external notifications, or connection to GitKraken.
- Product UI should explain user decisions, costs, and outcomes. Keep test controls and technical evidence in a separate labeled demo area.
- Add meaningful tests for business transitions and API permissions. Document run/test commands and limitations.
- Do not publish, contact GitKraken, use real accounts, or change external services as part of this build.
