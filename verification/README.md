# Independent verification

The supervisor runs checks against the builder's working app and records actual outcomes in `docs/verification.md`. Unit tests from the builder are one layer of evidence; browser/API observations are separate.

## Planned browser checks

1. On desktop, identify the blocked developer and why access is unavailable.
2. Request access twice; confirm one request exists.
3. Select the administrator in labeled demo controls and review the current quote.
4. Simulate a payment failure and observe the recovery state; then deliberately retry successfully.
5. Return to the developer and confirm the feature is accessible with an appropriate notification.
6. Reset to an available-seat scenario and check that approval does not purchase another seat.
7. Exercise the same primary journey on a narrow mobile viewport; check page errors and horizontal overflow.
8. Inspect screenshots and keyboard focus instead of relying only on DOM assertions.

## Planned API checks

Unauthorized/unknown actors, organization isolation, duplicate requests, current prices, stale quotes, replayed successes/failures, conflicting idempotency keys, concurrent approval, persistence across restart, and narrow reset behavior. Expected results are defined in `docs/brief.md`; successful assertions must inspect resulting counts and access, not only HTTP status codes.

## Test tooling

Runtime has no npm dependency. Browser verification uses Playwright 1.56.1 and the system Chromium executable, installed separately for the supervisor in `/tmp/access-lab-browser-tools`. Screenshots and machine-readable results are retained under `verification/artifacts/`.

Run the API checks from the project root. They create disposable SQLite databases, start and stop their own local app processes, and leave the running demonstration untouched:

```sh
python3 verification/verify_api.py
```

For the browser checks, install the test dependency separately and start a disposable demo:

```sh
npm install --ignore-scripts --no-audit --no-fund --prefix /tmp/access-lab-browser-tools playwright@1.56.1
python3 app/server.py --port 8765 --db /tmp/access-lab-review.sqlite3
```

Then, in another terminal:

```sh
node verification/browser.mjs
```

The browser script resets the sample data on this local server. By default it uses `/usr/bin/chromium`; set `CHROMIUM_PATH` to another installed Chromium executable if needed. `PLAYWRIGHT_MODULE` accepts an absolute module path, and `ACCESS_LAB_URL` selects a different loopback app URL. The browser script records its actual Chromium version; other versions have not been certified.

These commands need local process and socket permissions. A sandbox may require approval even though no external service is contacted by the tests.

## Completed checks

- `verify_api.py`: 14 black-box scenario groups against disposable server processes. Latest result: `artifacts/api-results.json`.
- `browser.mjs`: 12 check groups at desktop and mobile sizes, with selected computed contrast/font measurements, request interruption, and lost approval response. Latest result: `artifacts/browser-results.json`.
- `artifacts/ready-to-review.png`: final clean entry screen. Other screenshots illustrate cost preview, payment failure, successful access, and mobile layouts.
- `artifacts/initial-quote-check.png`: retained from an early verifier timing mistake; final tests wait for the quote control to finish loading.

The two network errors listed in the final browser report are deliberate test injections. The script asserts their count and rejects all unexpected browser errors.

Human usability sessions have not happened. Automated test results do not establish reduced support volume, higher conversion, or user satisfaction.
