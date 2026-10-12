import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from app.server import make_server


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = make_server(port=0, db_path=Path(cls.temp.name) / "api.sqlite3")
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.server.store.reset({"scenario": "full", "confirm": "RESET DEMO"})

    def call(self, method, path, actor=None, body=None, headers=None, raw=None):
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
        status, data = self.call("POST", "/api/requests", "maya", {})
        self.assertEqual(status, 201)
        return data["request"]["id"]

    def test_unknown_or_missing_identity_is_rejected(self):
        for actor in (None, "unknown", "eli OR 1=1"):
            status, _ = self.call("GET", "/api/workspace", actor)
            self.assertEqual(status, 401)

    def test_api_enforces_roles_and_organization_boundaries(self):
        request_id = self.request_id()
        body = {"quote_token": "0" * 64, "idempotency_key": "permission-check"}
        for endpoint in ("quote", "approve", "deny"):
            method = "GET" if endpoint == "quote" else "POST"
            payload = None if method == "GET" else (body if endpoint == "approve" else {})
            self.assertEqual(self.call(method, f"/api/requests/{request_id}/{endpoint}", "maya", payload)[0], 403)
            self.assertEqual(self.call(method, f"/api/requests/{request_id}/{endpoint}", "robin", payload)[0], 404)
        self.assertEqual(self.call("GET", f"/api/requests/{request_id}", "alex")[0], 404)
        self.assertEqual(self.call("POST", "/api/subscriptions", "maya", {"seat_count": 10})[0], 404)

    def test_api_full_journey_and_duplicate_request(self):
        self.assertEqual(self.call("GET", "/api/shared-workspace", "maya")[0], 403)
        request_id = self.request_id()
        self.assertEqual(self.call("POST", "/api/requests", "maya", {})[0], 200)
        status, quote = self.call("GET", f"/api/requests/{request_id}/quote", "eli")
        self.assertEqual(status, 200)
        self.assertEqual((quote["immediate_cents"], quote["next_period_cents"]), (600, 7200))
        body = {"quote_token": quote["token"], "idempotency_key": "http-approval"}
        status, result = self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)
        self.assertEqual((status, result["outcome"]), (200, "approved"))
        _, replay = self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)
        self.assertTrue(replay["replayed"])
        _, state = self.call("GET", "/api/workspace", "maya")
        self.assertTrue(state["access"]["enabled"])
        self.assertEqual(self.call("GET", "/api/shared-workspace", "maya")[0], 200)

    def test_prices_and_target_identity_cannot_be_supplied_by_client(self):
        self.assertEqual(self.call("POST", "/api/requests", "maya", {"user_id": "alex"})[0], 400)
        request_id = self.request_id()
        _, quote = self.call("GET", f"/api/requests/{request_id}/quote", "eli")
        body = {"quote_token": quote["token"], "idempotency_key": "spoofed-total", "amount_cents": 0}
        self.assertEqual(self.call("POST", f"/api/requests/{request_id}/approve", "eli", body)[0], 400)
        self.assertFalse(self.server.store.workspace("maya")["access"]["enabled"])

    def test_cross_origin_host_and_cross_site_requests_are_rejected(self):
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "null"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "http://127.0.0.1:9999"})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.call("GET", "/api/demo/info", headers={"Host": "evil.example:" + str(self.port)})[0], 403)
        self.assertEqual(self.call("POST", "/api/requests", "maya", {}, {"Origin": "http://127.0.0.1:" + str(self.port)})[0], 201)

    def test_json_validation_and_private_files(self):
        self.assertEqual(self.call("POST", "/api/requests", "maya", raw="{}")[0], 415)
        self.assertEqual(self.call("POST", "/api/requests", "maya", raw="{", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.call("POST", "/api/requests", "maya", body=[])[0], 400)
        self.assertEqual(self.call("GET", "/../app/domain.py")[0], 404)
        self.assertEqual(self.call("GET", "/docs/../app/domain.py")[0], 404)
        self.assertEqual(self.call("GET", "/data/access-lab.sqlite3")[0], 404)
        self.assertEqual(self.call("GET", "/docs/brief.md")[0], 200)

    def test_demo_reset_requires_explicit_confirmation_and_known_scenario(self):
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "full"})[0], 400)
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "unknown", "confirm": "RESET DEMO"})[0], 400)
        self.assertEqual(self.call("POST", "/api/demo/reset", body={"scenario": "spare", "confirm": "RESET DEMO"})[0], 200)

    def test_public_bind_is_rejected(self):
        with self.assertRaises(ValueError):
            make_server(host="0.0.0.0", port=0, db_path=Path(self.temp.name) / "never.sqlite3")


if __name__ == "__main__":
    unittest.main()
