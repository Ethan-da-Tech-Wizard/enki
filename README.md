# Access Lab

An independent portfolio prototype connecting team-seat requests, cost previews, simulated billing, access, and notifications.

**Status:** Local portfolio demonstration  
**Built with:** Python standard library, SQLite, HTML/CSS/JavaScript

[Project guide](docs/PROJECT_GUIDE.md) · [Every file explained](docs/FILE_GUIDE.md) · [Licenses and dependencies](docs/LICENSE_REVIEW.md)

## Start here

- [app/domain.py](app/domain.py) — Deterministic demo policy and persistent business transitions. Defines `DomainError`, `now`, `require_fields`, `valid_key`, `Store`.
- [app/server.py](app/server.py) — Loopback-only HTTP interface. Run: python3 -m app.server. Defines `is_loopback`, `Handler`, `make_server`, `main`.
- [docs/walkthrough.md](docs/walkthrough.md) — Documentation: Two-minute demo.
- [docs/case-study.md](docs/case-study.md) — Documentation: Access Lab — portfolio case study. Covers The question; Why this question; The product decision.

The following commands are taken from this project’s source/configuration. Install its prerequisites first.

```sh
python3 -m app.server
# Tests:
python3 -m unittest discover -s tests -v
```

[Detailed setup, usage, and development notes](PROJECT_NOTES.md) preserve the previous project documentation.

## Repository layout

| Path | Role |
| --- | --- |
| [app/](app/) | Application modules and user interface (7 tracked entries). |
| [docs/](docs/) | Project documentation, decisions, and reference material (12 tracked entries). |
| [tests/](tests/) | Automated checks and test fixtures (3 tracked entries). |
| [verification/](verification/) | Recorded verification evidence and supporting checks (17 tracked entries). |

## Scope and current limits

All people, prices, organizations, and payment results are fictional. This is an independent concept, not a GitKraken product. Keep the demo bound to loopback; source publication is not authorization to host the application publicly.

## License

Original project code retains **MIT** terms in [LICENSE](LICENSE). Third-party libraries, media, data, models, and tools retain their own terms. See the [license review](docs/LICENSE_REVIEW.md) and [dependency inventory](docs/DEPENDENCIES.csv).
