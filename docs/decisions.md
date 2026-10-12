# Decision log

| ID | Choice and reason | Tradeoff | How to verify |
| --- | --- | --- | --- |
| D-01 | One request-to-access journey connects the responsibilities in the role. | The prototype covers a narrow slice of team administration. | Trace AC-01 through AC-07 in `brief.md`. |
| D-02 | Use a separate builder agent; the root agent reviews code, runs checks, and sends revisions. | A second model adds coordination cost and still needs verification. | Read `supervision.md` and the test artifacts. |
| D-03 | Python standard library + SQLite + plain browser UI keeps setup small and permits offline runtime. | This is a local prototype stack; production would need a deployment/security design. | Start with the documented Python command in a clean environment. |
| D-04 | Use explicit deterministic billing/permission rules and integer cents. | Simplified prices and a fixed billing period cover the demo only. | Verify the displayed arithmetic and state-transition tests. |
| D-05 | Simulated payment and selectable demo identities make both sides easy to inspect. | This does not implement production authentication or payment processing. | Check the persistent demo label and README limitations. |
| D-06 | Keep facts, assumptions, and measured results separate. | User/business effectiveness remains unknown until observed. | Follow links in `evidence.md`; inspect the verification report. |
| D-07 | Keep advanced technical evidence outside normal user flows. | Requires a separate demo/evidence area. | Check developer/admin messages in the browser. |

Implementation discoveries and changes should be added with the relevant evidence and test, not backfilled as if known in advance.

| ID | Choice and reason | Tradeoff | How to verify |
| --- | --- | --- | --- |
| D-08 | Require a fresh server-generated quote fingerprint before approval. | An administrator must review again when relevant state changes. | Submit an approval against a stale seat count and inspect the conflict. |
| D-09 | Use a unique idempotency key for each deliberate payment attempt; reuse it on transport retries. | A failed attempt needs a new key for a deliberate retry. | Compare charge, notification, and seat counts after replay and concurrent submissions. |

Runtime references: Python's [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) supports the local database. Python explicitly describes [`http.server`](https://docs.python.org/3/library/http.server.html) as unsuitable for production; our use is limited to a loopback demo. A hosted version would need a production serving/authentication design before release.

## Review-driven changes

- D-10: Increase essential explanatory text and controls to a readable size and darken faint text. The selected text checks target at least 4.5:1 contrast, following the [W3C explanation of contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Our 12px minimum for selected supporting text is a project design choice, not a WCAG font-size requirement. These checks do not constitute a full accessibility audit.
- D-11: Restore a request button's original action after a transport failure so it accurately communicates that retry is available. Verify by intentionally aborting a browser request, then completing a retry.
- D-12: Format the stylesheet into readable rules and link the verification report from the demo controls. The code and the evidence should be inspectable by someone who did not watch the build.
