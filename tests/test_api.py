# ==============================================================================
# Program: test_api.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 19, 2026
# Purpose: Integration test suite for Access Lab HTTP REST API endpoints and middleware.
#          Spawns an in-process ThreadingHTTPServer instance on ephemeral loopback ports,
#          validating security perimeter boundaries (DNS rebinding guards, origin filtering,
#          and CSP injection), JSON payload constraints, role authorization checks,
#          and full transactional seat procurement journeys.
# ==============================================================================
"""Integration test suite executing live HTTP socket requests against loopback daemon."""

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from app.server import make_server


class ApiTests(unittest.TestCase):
    """Test suite exercising HTTP wire contracts, security guards, and error responses."""

    @classmethod
    def setUpClass(cls):
        """Spin up isolated in-memory HTTP server instance bound to loopback ephemeral port."""
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = make_server(port=0, db_path=Path(cls.temp.name) / "api.sqlite3")
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        """Cleanly terminate test server daemon and purge temporary filesystem fixtures."""
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        """Restore pristine baseline scenario state before each test execution."""
        self.server.store.reset({"scenario": "full", "confirm": "RESET DEMO"})

    def call(self, method, path, actor=None, body=None, headers=None, raw=None):
        """Execute raw HTTP request over loopback connection and parse response stream.
        
        Args:
            method: HTTP verb ('GET', 'POST').
            path: Target URI path.
            actor: Optional persona identifier injected into 'X-Demo-User' header.
            body: Optional JSON dictionary to serialize.
            headers: Optional dictionary of additional HTTP request headers.
            raw: Optional raw string payload overriding body serialization.
            
        Returns:
            tuple: (status_code, parsed_json_or_text_response)
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        send_headers = {}
        if actor is not None:
            send_headers["X-Demo-User"] = actor
        if body is not None:
            send_headers["Content-Type"] = "application/json"
            raw = json.dumps(body)
        send_headers.update(headers or {})
        
        conn.request(method, path, body=raw, headers=send_headers)
        response = conn.getresponse()
        data = response.read()
        status = response.status
        try:
            result = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            result = data.decode()
        conn.close()
        return status, result

    def request_id(self):
        """Submit a valid access request for 'maya' and assert 201 Created response."""
        status, data = self.call("POST", "/api/requests", "maya", {})
        self.assertEqual(status, 201)
        return data["request"]["id"]

    def test_unknown_or_missing_identity_is_rejected(self):
        """Verify that requests with missing, unauthorized, or malformed user headers are rejected with 401."""
        for actor in (None, "unknown", "eli OR 1=1"):
            status, _ = self.call("GET", "/api/workspace", actor)
            self.assertEqual(status, 401)

    def test_api_enforces_roles_and_organization_boundaries(self):
        """Assert RBAC and tenancy isolation: non-admins cannot review, and cross-org access is blocked."""
        request_id = self.request_id()
        body = {"quote_token": "0" * 64, "idempotency_key": "permission-check"}
        for endpoint in ("quote", "approve", "deny"):
            method = "GET" if endpoint == "quote" else "POST"
            payload = None if method == "GET" else (body if endpoint == "approve" else {})
            # Maya is a developer; administrative endpoints return 403 Forbidden
            self.assertEqual(self.call(method, f"/api/requests/{request_id}/{endpoint}", "maya", payload)[0], 403)
            # Robin belongs to organization 2; accessing organization 1 requests returns 404 Not Found
            self.assertEqual(self.call(method, f"/api/requests/{request_id}/{endpoint}", "robin", payload)[0], 404)
        self.assertEqual(self.call("GET", f"/api/requests/{request_id}", "alex")[0], 404)
        self.assertEqual(self.call("POST", "/api/subscriptions", "maya", {"seat_count": 10})[0], 404)

    def test_api_full_journey_and_duplicate_request(self):
        """Exercise complete HTTP access journey: request, quote calculation, approval, and workspace unlock."""
        # Initial shared workspace access blocked
        self.assertEqual(self.call("GET", "/api/shared-workspace", "maya")[0], 403)
        request_id = self.request_id()
        # Duplicate request returns existing record with status 200 OK
        self.assertEqual(self.call("POST", "/api/requests", "maya", {})[0], 200)
        
        # Admin requests cost quote
        status, quote = self.call("GET", f"/api/requests/{request_id}/quote", "eli")
        self.assertEqual(status, 200)
        self.assertEqual((quote["immediate_cents"], quote["next_period_cents"]), (600, 7200))
        
        # Admin approves with valid quote token and idempotency key
        body = {"quote_token": quote["token"], "idempotency_key": "http-approval"}
        status, result = self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)
        self.assertEqual((status, result["outcome"]), (200, "approved"))
        
        # Replay approval request returns cached outcome
        _, replay = self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)
        self.assertTrue(replay["replayed"])
        
        # Workspace is now enabled for requester
        _, state = self.call("GET", "/api/workspace", "maya")
        self.assertTrue(state["access"]["enabled"])
        self.assertEqual(self.call("GET", "/api/shared-workspace", "maya")[0], 200)

    def test_prices_and_target_identity_cannot_be_supplied_by_client(self):
        """Verify client tamper resistance: attempts to inject user_id or override pricing are rejected."""
        self.assertEqual(self.call("POST", "/api/requests", "maya", {"user_id": "alex"})[0], 400)
        request_id = self.request_id()
        _, quote = self.call("GET", f"/api/requests/{request_id}/quote", "eli")
        body = {"quote_token": quote["token"], "idempotency_key": "spoofed-total", "amount_cents": 0}
        self.assertEqual(self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)[0], 400)
        self.assertFalse(self.server.store.workspace("maya")["access"]["enabled"])

    def test_cross_origin_host_and_cross_site_requests_are_rejected(self):
        """Assert origin and Host header filtering to safeguard local loopback services against CSRF."""
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "null"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "http://127.0.0.1:9999"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.call("GET", "/api/demo/info", headers={"Host": "evil.example:" + str(self.port)})[0], 403)
        # Legitimate loopback origin is accepted
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "http://127.0.0.1:" + str(self.port)})[0], 201)

    def test_json_validation_and_private_files(self):
        """Verify strict Content-Type checking, JSON parsing boundaries, and directory traversal blocks."""
        self.assertEqual(self.call("POST", "/api/requests", "maya", raw="{}")[0], 415)
        self.assertEqual(self.call("POST", "/api/requests", "maya", raw="{", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.call("POST", "/api/requests", "maya", body=[])[0], 400)
        # Directory traversal attempts must return 404
        self.assertEqual(self.call("GET", "/../app/domain.py")[0], 404)
        self.assertEqual(self.call("GET", "/docs/../app/domain.py")[0], 404)
        self.assertEqual(self.call("GET", "/data/access-lab.sqlite3")[0], 404)
        # Whitelisted documentation file returns 200
        self.assertEqual(self.call("GET", "/docs/brief.md")[0], 200)

    def test_demo_reset_requires_explicit_confirmation_and_known_scenario(self):
        """Verify that demo resets require both valid confirmation string and registered scenario key."""
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "full"})[0], 400)
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "unknown", "confirm": "RESET DEMO"})[0], 400)
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "spare", "confirm": "RESET DEMO"})[0], 200)

    def test_public_bind_is_rejected(self):
        """Assert that attempting to bind server to non-loopback addresses (e.g., 0.0.0.0) raises ValueError."""
        with self.assertRaises(ValueError):
            make_server(host="0.0.0.0", port=0, db_path=Path(self.temp.name) / "never.sqlite3")


if __name__ == "__main__":
    unittest.main()
