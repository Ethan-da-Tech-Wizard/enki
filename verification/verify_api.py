# ==============================================================================
# Program: verify_api.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 19, 2026
# Purpose: Black-box verification harness validating live API contracts and daemon lifecycles.
#          Spawns isolated server processes on loopback interfaces, executes high-concurrency
#          stress checks (8 concurrent approvals), validates idempotency replay stability,
#          ensures cross-process persistence across hard restarts, and generates
#          machine-readable JSON validation artifacts.
# ==============================================================================
"""Supervisor-owned black-box checks against separate server processes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

# Application root directory anchor
ROOT = Path(__file__).resolve().parents[1]
# Filesystem path for verification report artifact
REPORT = ROOT / "verification" / "artifacts" / "api-results.json"
checks = []


def record(name: str, detail=None):
    """Record verification check outcome and output human-readable progress line."""
    checks.append({"name": name, "passed": True, "detail": detail})
    print("PASS " + name, flush=True)


class RunningApp:
    """Manages external subprocess lifecycle running Access Lab HTTP server on an ephemeral port."""
    
    def __init__(self, db: Path, log: Path):
        """Spawn server process, wait for startup banner, and parse dynamically assigned TCP port."""
        self.log = open(log, "a")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "app.server", "--port", "0", "--db", str(db)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
        )
        line = self.process.stdout.readline()
        match = re.search(r"http://127\.0\.0\.1:(\d+)", line)
        if not match:
            self.close()
            raise AssertionError("Server did not announce a local address: " + line + Path(log).read_text())
        self.port = int(match[1])
        # Consume subsequent informational banner lines
        self.process.stdout.readline()
        self.process.stdout.readline()

    def close(self):
        """Gracefully terminate background server process and release file descriptors."""
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=10)
        if self.process.stdout:
            self.process.stdout.close()
        self.log.close()

    def call(self, path: str, body=None, actor="maya", status=200, headers=None, raw=None) -> dict:
        """Issue an HTTP request over a loopback socket to the running subprocess.
        
        Args:
            path: Target URI path.
            body: Optional dictionary serialized as JSON.
            actor: Persona string passed in X-Demo-User header.
            status: Expected HTTP status code.
            headers: Additional request headers.
            raw: Optional raw string body overriding body serialization.
            
        Returns:
            dict: Parsed JSON response body.
        """
        request_headers = {"X-Demo-User": actor} if actor is not None else {}
        request_body = None
        if body is not None or raw is not None:
            request_headers["Content-Type"] = "application/json"
            request_body = raw if raw is not None else json.dumps(body)
        request_headers.update(headers or {})
        
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("POST" if request_body is not None else "GET", path, request_body, request_headers)
            response = connection.getresponse()
            data = response.read().decode()
            assert response.status == status, (path, response.status, status, data)
            return json.loads(data)
        finally:
            connection.close()

    def workspace(self, actor="eli") -> dict:
        """Query workspace snapshot for specified actor persona."""
        return self.call("/api/workspace", actor=actor)

    def reset(self, scenario="full"):
        """Reset demonstrative database state to initial scenario configuration."""
        self.call("/api/demo/reset", {"scenario": scenario, "confirm": "RESET DEMO"})

    def request(self) -> int:
        """Submit an access request for 'maya' and return the generated request ID."""
        return self.call("/api/requests", {}, status=201)["request"]["id"]

    def quote(self, request_id: int) -> dict:
        """Retrieve cost quote calculation for request ID from administrator persona perspective."""
        return self.call(f"/api/requests/{request_id}/quote", actor="eli")

    def approve(self, request_id: int, quote: dict, key: str, **kwargs) -> dict:
        """Submit approval transaction with quote token and idempotency key."""
        return self.call(f"/api/requests/{request_id}/approve", {"quote_token": quote["token"], "idempotency_key": key}, actor="eli", **kwargs)


app = None
failure = None

try:
    with tempfile.TemporaryDirectory(prefix="access-lab-independent-") as directory:
        db = Path(directory) / "demo.sqlite3"
        log = Path(directory) / "server.log"
        app = RunningApp(db, log)
        
        # 1. Verify baseline state and security rejection of unauthenticated/unassigned access
        initial = app.workspace("maya")
        assert initial["organization"]["seat_count"] == 5
        assert initial["organization"]["assigned_seats"] == 5
        assert initial["access"]["enabled"] is False
        assert "payments" not in initial and "members" not in initial
        for actor in (None, "unknown", "admin"):
            app.call("/api/workspace", actor=actor, status=401)
        app.call("/api/shared-workspace", status=403)
        record("Initial access is blocked and unknown/missing demo identities are rejected")

        # 2. Verify request deduplication and strict tenancy boundaries
        request_id = app.request()
        repeated = app.call("/api/requests", {})
        assert repeated["created"] is False and repeated["request"]["id"] == request_id
        assert len(app.workspace("maya")["requests"]) == 1
        quote = app.quote(request_id)
        for actor in ("maya", "alex"):
            app.call(f"/api/requests/{request_id}/approve", {"quote_token": quote["token"], "idempotency_key": "untrusted-attempt"}, actor=actor, status=403)
        for actor in ("alex", "quinn", "robin"):
            app.call(f"/api/requests/{request_id}", actor=actor, status=404)
        assert app.workspace("robin")["requests"] == []
        record("Duplicate requests are deduplicated; role and organization boundaries hold")

        # 3. Verify quote pricing precision and rejection of client-injected pricing overrides
        assert (quote["immediate_cents"], quote["next_period_cents"], quote["seats_after"]) == (600, 7200, 6)
        assert quote["immediate_cents"] == quote["seat_price_cents"] * quote["days_remaining"] // quote["period_days"]
        app.call("/api/requests", {"user_id": "eli"}, status=400)
        app.call(f"/api/requests/{request_id}/approve", {"quote_token": quote["token"], "idempotency_key": "fake-price-001", "amount_cents": 1}, actor="eli", status=400)
        assert not app.workspace()["payments"]
        record("Quote is $6 now/$72 next period and client-supplied prices/identity are rejected")

        # 4. Verify payment failure workflow, stable replay behavior, and rejection of stale quotes
        app.call("/api/demo/payment", {"result": "failure"})
        failed = app.approve(request_id, quote, "failed-attempt-001")
        assert failed["outcome"] == "payment_failed" and failed["charged_cents"] == 0
        snapshot = app.workspace()
        assert snapshot["organization"]["seat_count"] == 5
        assert snapshot["organization"]["assigned_seats"] == 5
        assert snapshot["requests"][0]["status"] == "payment_failed"
        assert len(snapshot["payments"]) == 1 and snapshot["payments"][0]["status"] == "failed"
        app.call("/api/demo/payment", {"result": "success"})
        replay = app.approve(request_id, quote, "failed-attempt-001")
        assert replay["replayed"] is True and replay["outcome"] == "payment_failed"
        assert app.workspace() == snapshot
        assert app.workspace("maya")["access"]["enabled"] is False
        stale = app.approve(request_id, quote, "new-key-old-quote", status=409)
        assert stale["error"]["code"] == "stale_quote"
        record("Failed payment persists without granting access; replay is stable and stale quote is rejected")

        # 5. Verify deliberate retry, seat increment, workspace access enablement, and safe replay
        fresh = app.quote(request_id)
        outcome = app.approve(request_id, fresh, "successful-retry-001")
        assert outcome["outcome"] == "approved" and outcome["charged_cents"] == 600
        approved = app.workspace()
        assert approved["organization"]["seat_count"] == approved["organization"]["assigned_seats"] == 6
        assert len([p for p in approved["payments"] if p["status"] == "succeeded"]) == 1
        assert app.workspace("maya")["access"]["enabled"] is True
        assert app.call("/api/shared-workspace")["sample"] is True
        replay = app.approve(request_id, fresh, "successful-retry-001")
        assert replay["replayed"] is True
        app.approve(request_id, quote, "successful-retry-001", status=409)
        assert app.workspace() == approved
        record("Deliberate retry grants real server-gated demo access; successful replay changes nothing")

        # 6. Verify notification isolation between personas
        admin_before_read = app.workspace()["notifications"]
        app.call("/api/notifications/read", {})
        assert all(n["read_at"] for n in app.workspace("maya")["notifications"])
        assert app.workspace()["notifications"] == admin_before_read
        record("Marking developer notifications read leaves administrator notifications unchanged")

        # 7. Verify persistent state consistency across cold process restarts
        persisted_admin, persisted_developer = app.workspace(), app.workspace("maya")
        app.close()
        app = RunningApp(db, log)
        assert app.workspace() == persisted_admin
        assert app.workspace("maya") == persisted_developer
        record("Requests, seats, transactions, notifications, and access survive a server process restart")

        # 8. High-concurrency stress testing: verify 8 parallel approvals execute safely
        for same_key in (True, False):
            app.reset()
            request_id = app.request()
            quote = app.quote(request_id)
            keys = ["concurrent-shared" if same_key else f"concurrent-distinct-{i}" for i in range(8)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(lambda key: app.approve(request_id, quote, key), keys))
            current = app.workspace()
            assert current["organization"]["seat_count"] == current["organization"]["assigned_seats"] == 6
            assert len(current["payments"]) == 1
            assert current["payments"][0]["amount_cents"] == 600
            assert len([e for e in current["activity"] if e["kind"] == "access_approved"]) == 1
            assert len([n for n in app.workspace("maya")["notifications"] if n["title"] == "You’re ready to collaborate"]) == 1
            if same_key:
                assert sum(not result["replayed"] for result in outcomes) == 1
            else:
                assert sum(result["outcome"] == "approved" for result in outcomes) == 1
            record(f"Eight concurrent {'same-key' if same_key else 'different-key'} approvals create one purchase and one access grant")

        # 9. Verify zero-cost spare seat allocation flow
        app.reset("spare")
        request_id = app.request()
        quote = app.quote(request_id)
        assert quote["immediate_cents"] == 0 and quote["next_period_cents"] == 7200
        app.call("/api/demo/payment", {"result": "failure"})
        result = app.approve(request_id, quote, "spare-seat-attempt")
        assert result["charged_cents"] == 0 and result["added_seats"] == 0
        assert app.workspace()["payments"] == []
        record("Spare-seat approval grants access without a payment attempt even with failure simulation selected")

        # 10. Verify quote fingerprint invalidation on reset
        app.reset()
        request_id = app.request()
        old_quote = app.quote(request_id)
        app.reset()
        assert app.request() == request_id
        error = app.approve(request_id, old_quote, "pre-reset-quote-key", status=409)
        assert error["error"]["code"] == "stale_quote"
        assert app.workspace()["payments"] == []
        record("Reset invalidates pre-reset cost previews even when request IDs are reused")

        # 11. Verify decline idempotency and re-request support
        app.call(f"/api/requests/{request_id}/deny", {}, actor="eli")
        denied_snapshot = app.workspace()
        app.call(f"/api/requests/{request_id}/deny", {}, actor="eli")
        assert app.workspace() == denied_snapshot
        assert app.workspace("maya")["access"]["enabled"] is False
        assert app.request() != request_id
        record("Decline is replay-safe, grants no access, and allows a new request")

        # 12. Verify perimeter validation against malformed inputs and cross-origin attacks
        app.call("/api/requests", {}, headers={"Origin": "https://example.com"}, status=403)
        app.call("/api/requests", {}, headers={"Host": "example.com"}, status=403)
        app.call("/api/requests", {}, headers={"Sec-Fetch-Site": "cross-site"}, status=403)
        app.call("/api/requests", {}, headers={"Content-Type": "text/plain"}, status=415)
        app.call("/api/requests", raw="[]", status=400)
        app.call("/api/demo/payment", {"result": []}, status=400)
        app.call("/api/demo/reset", {"scenario": [], "confirm": "RESET DEMO"}, status=400)
        app.call("/api/demo/reset", {"scenario": "full", "confirm": "no"}, status=400)
        record("Malformed inputs, unconfirmed resets, and cross-origin mutations receive explicit errors")

        # 13. Verify public host address binding rejection
        bind = subprocess.run([sys.executable, "-m", "app.server", "--host", "0.0.0.0", "--port", "0", "--db", str(db)], cwd=ROOT, capture_output=True, text=True, timeout=10)
        assert bind.returncode != 0 and "loopback" in bind.stderr
        record("Public binding is rejected")
        app.close()
        app = None
except Exception as error:
    failure = repr(error)
    print("FAIL " + failure, file=sys.stderr)
finally:
    if app:
        app.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"checkedAt": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0], "checks": checks, "passed": failure is None, "failure": failure}, indent=2) + "\n")

if failure:
    sys.exit(1)
