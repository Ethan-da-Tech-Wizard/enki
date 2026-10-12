# Files 1 of 1 — Access Lab

[All pages](../FILE_GUIDE.md) · [Project guide](../PROJECT_GUIDE.md)

| File | Role and useful details |
| --- | --- |
| [.gitignore](../../.gitignore) | Defines local data, credentials, dependencies, and generated outputs that Git should leave untracked. |
| [AGENTS.md](../../AGENTS.md) | Repository-specific development instructions and continuity rules for coding assistants. |
| [LICENSE](../../LICENSE) | Preserved license, copyright, or attribution terms; read the full text before reusing the covered component. |
| [PROJECT_NOTES.md](../../PROJECT_NOTES.md) | Preserved detailed setup, usage, architecture, and development notes from the earlier README. |
| [README.md](../../README.md) | Project overview, current status, entry points, setup navigation, and documentation links. |
| [app/__init__.py](../../app/__init__.py) | Access Lab: an independent, local portfolio demonstration. |
| [app/domain.py](../../app/domain.py) | Deterministic demo policy and persistent business transitions. Defines `DomainError`, `now`, `require_fields`, `valid_key`, `Store`. |
| [app/server.py](../../app/server.py) | Loopback-only HTTP interface. Run: python3 -m app.server. Defines `is_loopback`, `Handler`, `make_server`, `main`. |
| [app/static/app.js](../../app/static/app.js) | Source module for app; defines `api`, `announce`, `toast`, `savePersona`, `closeReview`, `refresh`, `statusBadge` and 22 more symbols. |
| [app/static/favicon.svg](../../app/static/favicon.svg) | Image or interface asset for favicon. Source/asset rights remain separate from software-license terms. |
| [app/static/index.html](../../app/static/index.html) | Browser document: Access Lab · Team access, made clear; provides page structure and may include inline styles or application logic. |
| [app/static/styles.css](../../app/static/styles.css) | Presentation rules for styles; controls layout, typography, color, states, and responsive behavior. |
| [docs/DEPENDENCIES.csv](../../docs/DEPENDENCIES.csv) | Machine-readable inventory of declared and locked dependencies, versions, reported licenses, and evidence URLs. |
| [docs/FILE_GUIDE.md](../../docs/FILE_GUIDE.md) | Index of the complete tracked-file guide, with one entry for every file and links to the paginated descriptions. |
| [docs/LICENSE_REVIEW.md](../../docs/LICENSE_REVIEW.md) | Original-code license, preserved component notices, dependency-license evidence, and unresolved distribution questions. |
| [docs/PROJECT_GUIDE.md](../../docs/PROJECT_GUIDE.md) | Maintainer orientation: purpose, important entry points, source layout, commands, and project-specific boundaries. |
| [docs/brief.md](../../docs/brief.md) | Documentation: Access Lab — product brief. Covers Purpose; Audience and hypothesis; First complete journey. |
| [docs/case-study.md](../../docs/case-study.md) | Documentation: Access Lab — portfolio case study. Covers The question; Why this question; The product decision. |
| [docs/decisions.md](../../docs/decisions.md) | Documentation: Decision log. Covers Review-driven changes. |
| [docs/evidence.md](../../docs/evidence.md) | Documentation: Evidence and assumptions. Covers Our assumptions; Unknowns; Proposed validation. |
| [docs/file-guide/files-001.md](../../docs/file-guide/files-001.md) | One page of the tracked-file catalog; links each listed path to its role and source-derived details. |
| [docs/supervision.md](../../docs/supervision.md) | Documentation: Builder supervision record. Covers Assignment 1 — initial implementation; Architecture checkpoint; Independent review 1. |
| [docs/verification.md](../../docs/verification.md) | Documentation: Verification report. Covers What is verified; Review findings and corrections; Reproduce. |
| [docs/walkthrough.md](../../docs/walkthrough.md) | Documentation: Two-minute demo. |
| [tests/__init__.py](../../tests/__init__.py) | Repeatable tests against disposable local demo databases. |
| [tests/test_api.py](../../tests/test_api.py) | Automated checks for api. Defines `ApiTests`. |
| [tests/test_domain.py](../../tests/test_domain.py) | Automated checks for domain. Defines `BusinessTests`. |
| [verification/README.md](../../verification/README.md) | Documentation: Independent verification. Covers Planned browser checks; Planned API checks; Test tooling. |
| [verification/artifacts/api-results.json](../../verification/artifacts/api-results.json) | Structured api results data; top-level fields: `checkedAt`, `python`, `checks`, `passed`, `failure`. |
| [verification/artifacts/browser-results.json](../../verification/artifacts/browser-results.json) | Structured browser results data; top-level fields: `checkedAt`, `url`, `browser`, `checks`, `contrastChecks`, `errors`, `injectedNetworkFailures`, `passed`, `failure`. |
| [verification/artifacts/desktop-access-granted.png](../../verification/artifacts/desktop-access-granted.png) | Recorded screenshot or visual review evidence for desktop access granted; 1440 × 1496 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/desktop-admin.png](../../verification/artifacts/desktop-admin.png) | Recorded screenshot or visual review evidence for desktop admin; 1440 × 1322 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/desktop-cost-preview.png](../../verification/artifacts/desktop-cost-preview.png) | Recorded screenshot or visual review evidence for desktop cost preview; 1440 × 1322 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/desktop-payment-failure.png](../../verification/artifacts/desktop-payment-failure.png) | Recorded screenshot or visual review evidence for desktop payment failure; 1440 × 1322 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/desktop-start.png](../../verification/artifacts/desktop-start.png) | Recorded screenshot or visual review evidence for desktop start; 1440 × 1075 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/failure.png](../../verification/artifacts/failure.png) | Recorded screenshot or visual review evidence for failure; 1440 × 1075 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/initial-quote-check.png](../../verification/artifacts/initial-quote-check.png) | Recorded screenshot or visual review evidence for initial quote check; 1440 × 1255 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/mobile-access-granted.png](../../verification/artifacts/mobile-access-granted.png) | Recorded screenshot or visual review evidence for mobile access granted; 390 × 2252 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/mobile-cost-preview.png](../../verification/artifacts/mobile-cost-preview.png) | Recorded screenshot or visual review evidence for mobile cost preview; 390 × 2287 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/mobile-start.png](../../verification/artifacts/mobile-start.png) | Recorded screenshot or visual review evidence for mobile start; 390 × 1877 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/ready-to-review.png](../../verification/artifacts/ready-to-review.png) | Recorded screenshot or visual review evidence for ready to review; 1440 × 1075 pixels. Source/asset rights remain separate from software-license terms. |
| [verification/artifacts/source-sha256.json](../../verification/artifacts/source-sha256.json) | Structured source sha256 data; top-level fields: `app/__init__.py`, `app/domain.py`, `app/server.py`, `app/static/app.js`, `app/static/favicon.svg`, `app/static/index.html`, `app/static/styles.css`, `tests/__init__.py`, `tests/test_api.py`. |
| [verification/browser.mjs](../../verification/browser.mjs) | Source module for browser; defines `record`, `api`, `screenshot`, `visibleText`, `showDemo`, `persona`, `payment` and 9 more symbols. |
| [verification/verify_api.py](../../verification/verify_api.py) | Supervisor-owned black-box checks against separate server processes. Defines `record`, `RunningApp`. |
