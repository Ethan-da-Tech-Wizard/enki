from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.domain import DomainError, Store


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "test.sqlite3"
        self.store = Store(self.db_path)

    def request(self, actor="maya"):
        return self.store.create_request(actor, {})["request"]["id"]

    def approval(self, request_id, key="approval-001", actor="eli"):
        return {"quote_token": self.store.quote(actor, request_id)["token"], "idempotency_key": key}

    def scalar(self, sql):
        with self.store.connection() as db:
            return db.execute(sql).fetchone()[0]

    def error(self, code, fn, *args):
        with self.assertRaises(DomainError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_full_seat_journey_is_atomic_and_costed_in_cents(self):
        initial = self.store.workspace("maya")
        self.assertFalse(initial["access"]["enabled"])
        self.assertEqual(initial["organization"]["available_seats"], 0)
        request_id = self.request()
        quote = self.store.quote("eli", request_id)
        self.assertEqual((quote["immediate_cents"], quote["next_period_cents"]), (600, 7200))
        self.assertEqual((quote["seat_price_cents"], quote["days_remaining"], quote["period_days"]), (1200, 15, 30))
        result = self.store.approve("eli", request_id, self.approval(request_id))
        self.assertEqual(result["outcome"], "approved")
        after = self.store.workspace("maya")
        self.assertTrue(after["access"]["enabled"])
        self.assertEqual((after["organization"]["seat_count"], after["organization"]["assigned_seats"]), (6, 6))
        self.assertEqual(after["requests"][0]["status"], "approved")
        self.assertEqual(after["actor"]["membership"], "member")
        self.assertEqual(self.scalar("SELECT SUM(amount_cents) FROM payments WHERE status='succeeded'"), 600)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM events WHERE kind='access_approved'"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notifications WHERE title IN ('You’re ready to collaborate','Workspace access granted')"), 2)

    def test_duplicate_request_clicks_and_concurrent_requests_create_one(self):
        barrier = threading.Barrier(4)
        def request(_):
            barrier.wait()
            return self.store.create_request("maya", {})
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(request, range(4)))
        self.assertEqual(len({r["request"]["id"] for r in results}), 1)
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM requests"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notifications"), 2)

    def test_success_replay_and_different_key_do_not_duplicate(self):
        request_id = self.request()
        body = self.approval(request_id)
        result = self.store.approve("eli", request_id, body)
        replay = self.store.approve("eli", request_id, body)
        self.assertTrue(replay["replayed"])
        self.assertEqual(result, {**replay, "replayed": False})
        later = self.store.approve("eli", request_id, {**body, "idempotency_key": "approval-002"})
        self.assertEqual(later["outcome"], "already_approved")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM assignments WHERE user_id='maya'"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notifications"), 4)

    def test_concurrent_approvals_same_key_are_replays(self):
        request_id = self.request()
        body = self.approval(request_id)
        barrier = threading.Barrier(6)
        def approve(_):
            barrier.wait()
            return self.store.approve("eli", request_id, body)
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(approve, range(6)))
        self.assertEqual(sum(not r["replayed"] for r in results), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM events WHERE kind='access_approved'"), 1)

    def test_concurrent_different_keys_cannot_double_purchase(self):
        request_id = self.request()
        body = self.approval(request_id)
        barrier = threading.Barrier(4)
        def approve(i):
            barrier.wait()
            return self.store.approve("eli", request_id, {**body, "idempotency_key": "concurrent-%d" % i})
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(approve, range(4)))
        self.assertEqual(sum(r["outcome"] == "approved" for r in results), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 1)
        self.assertEqual(self.scalar("SELECT seat_count FROM organizations WHERE id=1"), 6)

    def test_failed_attempt_replay_and_deliberate_retry(self):
        request_id = self.request()
        body = self.approval(request_id)
        self.store.demo_payment({"result": "failure"})
        result = self.store.approve("eli", request_id, body)
        self.assertEqual(result["outcome"], "payment_failed")
        self.assertEqual(result["charged_cents"], 0)
        state = self.store.workspace("maya")
        self.assertFalse(state["access"]["enabled"])
        self.assertEqual(state["organization"]["seat_count"], 5)
        self.assertEqual(state["organization"]["assigned_seats"], 5)
        self.assertEqual(state["requests"][0]["status"], "payment_failed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments WHERE status='succeeded'"), 0)
        self.store.demo_payment({"result": "success"})
        replay = self.store.approve("eli", request_id, body)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["outcome"], "payment_failed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 1)
        self.error("stale_quote", self.store.approve, "eli", request_id, {**body, "idempotency_key": "retry-old-preview"})
        result = self.store.approve("eli", request_id, self.approval(request_id, "retry-current-preview"))
        self.assertEqual(result["outcome"], "approved")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments WHERE status='succeeded'"), 1)

    def test_key_payload_mismatch_is_rejected(self):
        request_id = self.request()
        body = self.approval(request_id)
        self.store.demo_payment({"result": "failure"})
        self.store.approve("eli", request_id, body)
        self.error("idempotency_conflict", self.store.approve, "eli", request_id, self.approval(request_id))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 1)

    def test_spare_seat_assigns_without_payment_even_when_simulator_fails(self):
        self.store.reset({"scenario": "spare", "confirm": "RESET DEMO"})
        self.store.demo_payment({"result": "failure"})
        request_id = self.request()
        quote = self.store.quote("eli", request_id)
        self.assertEqual((quote["immediate_cents"], quote["next_period_cents"], quote["added_seats"]), (0, 7200, 0))
        result = self.store.approve("eli", request_id, self.approval(request_id))
        self.assertEqual(result["outcome"], "approved")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 0)
        self.assertEqual(self.scalar("SELECT seat_count FROM organizations WHERE id=1"), 6)

    def test_stale_preview_requires_explicit_review(self):
        request_id = self.request()
        body = self.approval(request_id)
        with self.store.transaction() as db:
            db.execute("UPDATE organizations SET seat_count=6,revision=revision+1 WHERE id=1")
        self.error("stale_quote", self.store.approve, "eli", request_id, body)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 0)
        self.assertFalse(self.store.workspace("maya")["access"]["enabled"])
        self.assertEqual(self.store.quote("eli", request_id)["immediate_cents"], 0)

    def test_reset_invalidates_old_quotes_even_if_request_id_is_reused(self):
        request_id = self.request()
        body = self.approval(request_id)
        self.store.reset({"scenario": "full", "confirm": "RESET DEMO"})
        self.assertEqual(self.request(), request_id)
        self.error("stale_quote", self.store.approve, "eli", request_id, body)

    def test_mid_transition_failure_rolls_back_purchase_assignment_and_events(self):
        request_id = self.request()
        body = self.approval(request_id)
        with patch.object(self.store, "_notify", side_effect=RuntimeError("forced storage failure")):
            with self.assertRaises(RuntimeError):
                self.store.approve("eli", request_id, body)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM payments"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM assignments WHERE user_id='maya'"), 0)
        self.assertEqual(self.scalar("SELECT seat_count FROM organizations WHERE id=1"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM events WHERE kind='access_approved'"), 0)
        self.assertEqual(self.store.request_detail("maya", request_id)["status"], "pending")

    def test_self_approval_and_cross_org_access_are_forbidden(self):
        request_id = self.request()
        self.error("admin_required", self.store.quote, "maya", request_id)
        self.error("request_not_found", self.store.quote, "robin", request_id)
        self.error("request_not_found", self.store.request_detail, "alex", request_id)
        self.error("request_not_found", self.store.request_detail, "quinn", request_id)
        with self.store.transaction() as db:
            db.execute("DELETE FROM assignments WHERE user_id='eli'")
        own_request = self.request("eli")
        self.error("self_approval_forbidden", self.store.quote, "eli", own_request)
        self.error("self_approval_forbidden", self.store.approve, "eli", own_request, {"quote_token": "0" * 64, "idempotency_key": "self-approval"})

    def test_developer_data_is_private_and_access_comes_from_membership(self):
        request_id = self.request()
        maya = self.store.workspace("maya")
        alex = self.store.workspace("alex")
        self.assertNotIn("payments", maya)
        self.assertNotIn("members", maya)
        self.assertEqual(alex["requests"], [])
        self.assertEqual(alex["notifications"], [])
        self.assertEqual(alex["activity"], [])
        self.store.approve("eli", request_id, self.approval(request_id))
        with self.store.transaction() as db:
            db.execute("DELETE FROM assignments WHERE user_id='maya'")
        state = self.store.workspace("maya")
        self.assertEqual(state["requests"][0]["status"], "approved")
        self.assertFalse(state["access"]["enabled"])

    def test_deny_is_replay_safe_and_developer_can_request_again(self):
        request_id = self.request()
        self.store.deny("eli", request_id, {})
        self.assertTrue(self.store.deny("eli", request_id, {})["replayed"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM events WHERE kind='access_denied'"), 1)
        self.error("request_closed", self.store.quote, "eli", request_id)
        next_request = self.request()
        self.assertNotEqual(request_id, next_request)

    def test_saved_state_survives_store_reopening(self):
        request_id = self.request()
        self.store.approve("eli", request_id, self.approval(request_id))
        reopened = Store(self.db_path)
        state = reopened.workspace("maya")
        self.assertTrue(state["access"]["enabled"])
        self.assertEqual(state["organization"]["seat_count"], 6)
        self.assertEqual(state["requests"][0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
