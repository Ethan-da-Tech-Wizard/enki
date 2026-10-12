# Access Lab

An independent portfolio prototype connecting team-seat requests, cost previews, simulated billing, access, and notifications.

**Status:** Local portfolio demonstration  
**Built with:** Python standard library, SQLite, HTML/CSS/JavaScript

## Reading order

1. Read the root README for project purpose and setup navigation.
2. Follow the entry points below to find the implementation.
3. Use the file guide to locate individual modules, tests, assets, and configuration.
4. Check component licenses before redistributing dependencies or assets.

## Important paths

- [app/domain.py](../app/domain.py) — Deterministic demo policy and persistent business transitions. Defines `DomainError`, `now`, `require_fields`, `valid_key`, `Store`.
- [app/server.py](../app/server.py) — Loopback-only HTTP interface. Run: python3 -m app.server. Defines `is_loopback`, `Handler`, `make_server`, `main`.
- [docs/walkthrough.md](../docs/walkthrough.md) — Documentation: Two-minute demo.
- [docs/case-study.md](../docs/case-study.md) — Documentation: Access Lab — portfolio case study. Covers The question; Why this question; The product decision.

## Structure

| Path | Role |
| --- | --- |
| [app/](../app/) | Application modules and user interface (7 tracked entries). |
| [docs/](../docs/) | Project documentation, decisions, and reference material (12 tracked entries). |
| [tests/](../tests/) | Automated checks and test fixtures (3 tracked entries). |
| [verification/](../verification/) | Recorded verification evidence and supporting checks (17 tracked entries). |

## Useful commands

Run from the repository root after following the documented prerequisites.

```sh
python3 -m app.server
# Tests:
python3 -m unittest discover -s tests -v
```

## Scope

All people, prices, organizations, and payment results are fictional. This is an independent concept, not a GitKraken product. Keep the demo bound to loopback; source publication is not authorization to host the application publicly.

## Maintaining the guide

The file catalog is a source-inspection snapshot, not proof that every runtime path works. Update it when moving files or changing module responsibilities. The 2026-10-12 documentation review did not run every application, deploy services, or validate all historical performance claims.
