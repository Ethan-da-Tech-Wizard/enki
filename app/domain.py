"""Deterministic demo policy and persistent business transitions.

All prices, identities, and billing rules here are invented sample policy.
Permissions are evaluated against a selected demo identity, not a real login.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid


SEAT_PRICE_CENTS = 1200
PERIOD_DAYS = 30
DAYS_REMAINING = 15
SCENARIOS = {"full": "Five seats, all occupied", "spare": "One available paid seat"}


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def require_fields(body, allowed, required=()):
    if not isinstance(body, dict):
        raise DomainError(400, "invalid_body", "Send a JSON object.")
    extra = set(body) - set(allowed)
    missing = set(required) - set(body)
    if extra or missing:
        raise DomainError(400, "invalid_fields", "The request has missing or unsupported fields.")


def valid_key(key):
    if not isinstance(key, str) or not 8 <= len(key) <= 100 or not all(c.isalnum() or c in "-_" for c in key):
        raise DomainError(400, "invalid_idempotency_key", "Use an 8–100 character attempt key with letters, numbers, hyphens, or underscores.")


SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, seat_count INTEGER NOT NULL CHECK(seat_count > 0),
    revision INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','developer')),
    membership TEXT NOT NULL CHECK(membership IN ('invited','member')),
    UNIQUE(id, org_id)
);
CREATE TABLE IF NOT EXISTS assignments (
    user_id TEXT PRIMARY KEY, org_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL, FOREIGN KEY(user_id, org_id) REFERENCES users(id, org_id)
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, user_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','payment_failed','approved','denied')),
    attempt_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id, org_id) REFERENCES users(id, org_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_request ON requests(org_id, user_id)
    WHERE status IN ('pending','payment_failed');
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL REFERENCES organizations(id),
    request_id INTEGER NOT NULL REFERENCES requests(id), actor_id TEXT NOT NULL REFERENCES users(id),
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    status TEXT NOT NULL CHECK(status IN ('succeeded','failed')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, user_id TEXT NOT NULL,
    request_id INTEGER REFERENCES requests(id), title TEXT NOT NULL, message TEXT NOT NULL,
    created_at TEXT NOT NULL, read_at TEXT,
    FOREIGN KEY(user_id, org_id) REFERENCES users(id, org_id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL REFERENCES organizations(id),
    actor_id TEXT REFERENCES users(id), subject_user_id TEXT REFERENCES users(id),
    request_id INTEGER REFERENCES requests(id), kind TEXT NOT NULL,
    summary TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    actor_id TEXT NOT NULL REFERENCES users(id), attempt_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(actor_id, attempt_key)
);
"""


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM demo_state WHERE key='epoch'").fetchone():
                self._seed(db, "full")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    def _seed(self, db, scenario):
        timestamp = now()
        for table in ("attempts", "events", "notifications", "payments", "requests", "assignments", "users", "organizations", "demo_state"):
            db.execute("DELETE FROM " + table)
        db.execute("DELETE FROM sqlite_sequence")
        db.executemany("INSERT INTO demo_state(key,value) VALUES(?,?)", [
            ("epoch", str(uuid.uuid4())), ("scenario", scenario), ("payment_result", "success")])
        db.executemany("INSERT INTO organizations(id,name,seat_count) VALUES(?,?,?)", [
            (1, "Northstar Studio", 5 if scenario == "full" else 6), (2, "Juniper Labs", 1)])
        users = [
            ("maya", 1, "Maya Chen", "maya@northstar.example", "developer", "invited"),
            ("eli", 1, "Eli Brooks", "eli@northstar.example", "admin", "member"),
            ("alex", 1, "Alex Morgan", "alex@northstar.example", "developer", "member"),
            ("sam", 1, "Sam Rivera", "sam@northstar.example", "developer", "member"),
            ("jordan", 1, "Jordan Lee", "jordan@northstar.example", "developer", "member"),
            ("noor", 1, "Noor Patel", "noor@northstar.example", "developer", "member"),
            ("robin", 2, "Robin Ellis", "robin@juniper.example", "admin", "member"),
            ("quinn", 2, "Quinn Taylor", "quinn@juniper.example", "developer", "invited"),
        ]
        db.executemany("INSERT INTO users VALUES(?,?,?,?,?,?)", users)
        db.executemany("INSERT INTO assignments VALUES(?,?,?)", [
            (who, org, timestamp) for who, org in [("eli", 1), ("alex", 1), ("sam", 1), ("jordan", 1), ("noor", 1), ("robin", 2)]])
        self._event(db, 1, None, None, None, "scenario_ready", "Sample workspace is ready", {"scenario": scenario})

    def actor(self, db, actor_id):
        if not isinstance(actor_id, str) or not actor_id or len(actor_id) > 80:
            raise DomainError(401, "demo_identity_required", "Choose a valid demo identity.")
        row = db.execute("SELECT * FROM users WHERE id=?", (actor_id,)).fetchone()
        if row is None:
            raise DomainError(401, "unknown_demo_identity", "This demo identity is not available.")
        return dict(row)

    def _request(self, db, actor, request_id, admin=False):
        if admin and actor["role"] != "admin":
            raise DomainError(403, "admin_required", "Only your organization’s administrator can review requests.")
        row = db.execute("SELECT r.*,u.name AS requester_name,u.email AS requester_email FROM requests r JOIN users u ON u.id=r.user_id WHERE r.id=? AND r.org_id=?", (request_id, actor["org_id"])).fetchone()
        if row is None or (actor["role"] != "admin" and row["user_id"] != actor["id"]):
            raise DomainError(404, "request_not_found", "This request is not available to this identity.")
        return dict(row)

    def _event(self, db, org_id, actor_id, subject_id, request_id, kind, summary, detail):
        db.execute("INSERT INTO events(org_id,actor_id,subject_user_id,request_id,kind,summary,detail_json,created_at) VALUES(?,?,?,?,?,?,?,?)", (org_id, actor_id, subject_id, request_id, kind, summary, json.dumps(detail, sort_keys=True), now()))

    def _notify(self, db, org_id, user_id, request_id, title, message):
        db.execute("INSERT INTO notifications(org_id,user_id,request_id,title,message,created_at) VALUES(?,?,?,?,?,?)", (org_id, user_id, request_id, title, message, now()))

    def _organization(self, db, org_id):
        org = dict(db.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone())
        org["assigned_seats"] = db.execute("SELECT COUNT(*) FROM assignments WHERE org_id=?", (org_id,)).fetchone()[0]
        org["available_seats"] = org["seat_count"] - org["assigned_seats"]
        org["next_period_cents"] = org["seat_count"] * SEAT_PRICE_CENTS
        return org

    def workspace(self, actor_id):
        with self.connection() as db:
            db.execute("BEGIN")
            actor = self.actor(db, actor_id)
            org = self._organization(db, actor["org_id"])
            assigned = db.execute("SELECT 1 FROM assignments WHERE user_id=? AND org_id=?", (actor_id, actor["org_id"])).fetchone() is not None
            request_filter = "r.org_id=?" if actor["role"] == "admin" else "r.org_id=? AND r.user_id=?"
            params = (actor["org_id"],) if actor["role"] == "admin" else (actor["org_id"], actor_id)
            requests = [dict(r) for r in db.execute("SELECT r.*,u.name AS requester_name,u.email AS requester_email FROM requests r JOIN users u ON u.id=r.user_id WHERE " + request_filter + " ORDER BY r.id DESC", params)]
            event_filter = "org_id=?" if actor["role"] == "admin" else "org_id=? AND subject_user_id=?"
            activity = [dict(r) for r in db.execute("SELECT id,kind,summary,created_at,request_id FROM events WHERE " + event_filter + " ORDER BY id DESC LIMIT 30", params)]
            result = {
                "actor": actor, "organization": org,
                "access": {"assigned": assigned, "enabled": assigned and actor["membership"] == "member"},
                "plan": {"name": "Team", "currency": "USD", "seat_price_cents": SEAT_PRICE_CENTS, "period_days": PERIOD_DAYS, "days_remaining": DAYS_REMAINING, "sample": True},
                "requests": requests, "activity": activity,
                "notifications": [dict(r) for r in db.execute("SELECT id,request_id,title,message,created_at,read_at FROM notifications WHERE user_id=? AND org_id=? ORDER BY id DESC LIMIT 30", (actor_id, actor["org_id"]))],
            }
            if actor["role"] == "admin":
                result["members"] = [dict(r) for r in db.execute("SELECT u.id,u.name,u.email,u.role,u.membership,CASE WHEN a.user_id IS NULL THEN 0 ELSE 1 END AS assigned FROM users u LEFT JOIN assignments a ON a.user_id=u.id AND a.org_id=u.org_id WHERE u.org_id=? ORDER BY assigned DESC,u.name", (actor["org_id"],))]
                result["payments"] = [dict(r) for r in db.execute("SELECT p.*,u.name AS requester_name FROM payments p JOIN requests r ON r.id=p.request_id JOIN users u ON u.id=r.user_id WHERE p.org_id=? ORDER BY p.id DESC LIMIT 30", (actor["org_id"],))]
            return result

    def request_detail(self, actor_id, request_id):
        with self.connection() as db:
            return self._request(db, self.actor(db, actor_id), request_id)

    def shared_workspace(self, actor_id):
        with self.connection() as db:
            actor = self.actor(db, actor_id)
            assigned = db.execute("SELECT 1 FROM assignments WHERE user_id=? AND org_id=?", (actor_id, actor["org_id"])).fetchone()
            if not assigned or actor["membership"] != "member":
                raise DomainError(403, "seat_required", "An assigned team seat is required to open the shared review workspace.")
            return {"title": "Your shared review workspace", "sample": True,
                    "review": {"title": "Navigation update", "description": "A shared place for the team’s next review.", "status": "Ready for review"}}

    def create_request(self, actor_id, body):
        require_fields(body, ())
        with self.transaction() as db:
            actor = self.actor(db, actor_id)
            if db.execute("SELECT 1 FROM assignments WHERE user_id=?", (actor_id,)).fetchone():
                raise DomainError(409, "already_has_access", "You already have a seat in this workspace.")
            active = db.execute("SELECT id FROM requests WHERE user_id=? AND org_id=? AND status IN ('pending','payment_failed')", (actor_id, actor["org_id"])).fetchone()
            if active:
                return {"created": False, "request": self._request(db, actor, active["id"])}
            timestamp = now()
            cur = db.execute("INSERT INTO requests(org_id,user_id,status,created_at,updated_at) VALUES(?,?,'pending',?,?)", (actor["org_id"], actor_id, timestamp, timestamp))
            request_id = cur.lastrowid
            self._event(db, actor["org_id"], actor_id, actor_id, request_id, "access_requested", actor["name"] + " requested workspace access", {})
            for admin in db.execute("SELECT id FROM users WHERE org_id=? AND role='admin'", (actor["org_id"],)):
                self._notify(db, actor["org_id"], admin["id"], request_id, "An access request needs review", actor["name"] + " would like to join the shared review workspace.")
            self._notify(db, actor["org_id"], actor_id, request_id, "Your request was sent", "Your administrator can review the request and confirm any seat cost.")
            return {"created": True, "request": self._request(db, actor, request_id)}

    def _quote(self, db, actor, request_id):
        request = self._request(db, actor, request_id, admin=True)
        if request["user_id"] == actor["id"]:
            raise DomainError(403, "self_approval_forbidden", "An administrator cannot approve their own request.")
        if request["status"] not in ("pending", "payment_failed"):
            raise DomainError(409, "request_closed", "This request has already been resolved.")
        org = self._organization(db, actor["org_id"])
        added = 1 if org["available_seats"] <= 0 else 0
        immediate = added * SEAT_PRICE_CENTS * DAYS_REMAINING // PERIOD_DAYS
        payload = {
            "epoch": db.execute("SELECT value FROM demo_state WHERE key='epoch'").fetchone()[0],
            "request_id": request_id, "request_status": request["status"], "attempt_count": request["attempt_count"],
            "org_id": org["id"], "revision": org["revision"], "seat_count": org["seat_count"], "assigned_seats": org["assigned_seats"],
        }
        token = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return {"token": token, "request_id": request_id, "requester_name": request["requester_name"],
                "sample": True, "currency": "USD", "added_seats": added, "current_seats": org["seat_count"],
                "current_assigned": org["assigned_seats"], "available_seats": org["available_seats"],
                "seats_after": org["seat_count"] + added, "assigned_after": org["assigned_seats"] + 1,
                "immediate_cents": immediate, "next_period_cents": (org["seat_count"] + added) * SEAT_PRICE_CENTS,
                "seat_price_cents": SEAT_PRICE_CENTS, "period_days": PERIOD_DAYS, "days_remaining": DAYS_REMAINING}

    def quote(self, actor_id, request_id):
        with self.connection() as db:
            db.execute("BEGIN")
            return self._quote(db, self.actor(db, actor_id), request_id)

    def approve(self, actor_id, request_id, body):
        require_fields(body, ("quote_token", "idempotency_key"), ("quote_token", "idempotency_key"))
        valid_key(body["idempotency_key"])
        if not isinstance(body["quote_token"], str) or len(body["quote_token"]) != 64:
            raise DomainError(400, "invalid_quote", "Review the current cost preview before approving.")
        payload_hash = hashlib.sha256(json.dumps({"request_id": request_id, **body}, sort_keys=True).encode()).hexdigest()
        with self.transaction() as db:
            actor = self.actor(db, actor_id)
            request = self._request(db, actor, request_id, admin=True)
            if actor["id"] == request["user_id"]:
                raise DomainError(403, "self_approval_forbidden", "An administrator cannot approve their own request.")
            prior = db.execute("SELECT * FROM attempts WHERE actor_id=? AND attempt_key=?", (actor_id, body["idempotency_key"])).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise DomainError(409, "idempotency_conflict", "This attempt key was already used for a different approval. Start a new review.")
                return {**json.loads(prior["response_json"]), "replayed": True}
            if request["status"] == "approved":
                return {"outcome": "already_approved", "request_id": request_id, "replayed": False, "message": "Access was already granted. No additional purchase was made."}
            quote = self._quote(db, actor, request_id)
            if quote["token"] != body["quote_token"]:
                raise DomainError(409, "stale_quote", "The team or request changed. Review the updated cost before approving.")
            timestamp = now()
            payment_id = None
            payment_result = db.execute("SELECT value FROM demo_state WHERE key='payment_result'").fetchone()[0]
            if quote["immediate_cents"]:
                succeeded = payment_result == "success"
                cur = db.execute("INSERT INTO payments(org_id,request_id,actor_id,amount_cents,status,created_at) VALUES(?,?,?,?,?,?)", (actor["org_id"], request_id, actor_id, quote["immediate_cents"], "succeeded" if succeeded else "failed", timestamp))
                payment_id = cur.lastrowid
                if not succeeded:
                    db.execute("UPDATE requests SET status='payment_failed',attempt_count=attempt_count+1,updated_at=? WHERE id=?", (timestamp, request_id))
                    self._event(db, actor["org_id"], actor_id, request["user_id"], request_id, "payment_failed", "Payment did not go through; access is still pending", {"simulated": True, "amount_cents": quote["immediate_cents"], "payment_id": payment_id})
                    self._notify(db, actor["org_id"], actor_id, request_id, "Payment did not go through", "No charge succeeded and no seat was added. Review the request and try again when ready.")
                    self._notify(db, actor["org_id"], request["user_id"], request_id, "Your request is still open", "Your administrator needs to resolve a payment issue before a new seat can be added.")
                    result = {"outcome": "payment_failed", "request_id": request_id, "payment_id": payment_id, "charged_cents": 0, "attempted_cents": quote["immediate_cents"], "replayed": False, "message": "Simulated payment failed. No charge succeeded, no seat was added, and the request is ready to retry."}
                    self._save_attempt(db, actor_id, body, payload_hash, result)
                    return result
            db.execute("UPDATE organizations SET seat_count=seat_count+?,revision=revision+1 WHERE id=?", (quote["added_seats"], actor["org_id"]))
            db.execute("INSERT INTO assignments(user_id,org_id,assigned_at) VALUES(?,?,?)", (request["user_id"], actor["org_id"], timestamp))
            db.execute("UPDATE users SET membership='member' WHERE id=?", (request["user_id"],))
            db.execute("UPDATE requests SET status='approved',attempt_count=attempt_count+1,updated_at=? WHERE id=?", (timestamp, request_id))
            self._event(db, actor["org_id"], actor_id, request["user_id"], request_id, "access_approved", request["requester_name"] + " now has workspace access", {"added_seats": quote["added_seats"], "charged_cents": quote["immediate_cents"], "simulated": True, "payment_id": payment_id})
            self._notify(db, actor["org_id"], request["user_id"], request_id, "You’re ready to collaborate", "Your administrator approved your request. The shared review workspace is now available.")
            self._notify(db, actor["org_id"], actor_id, request_id, "Workspace access granted", request["requester_name"] + " has a seat. " + ("A new seat was added with a simulated payment." if quote["added_seats"] else "An existing paid seat was assigned, with no additional charge."))
            result = {"outcome": "approved", "request_id": request_id, "payment_id": payment_id, "charged_cents": quote["immediate_cents"], "added_seats": quote["added_seats"], "seats_after": quote["seats_after"], "assigned_after": quote["assigned_after"], "replayed": False, "message": request["requester_name"] + " now has access to the shared review workspace."}
            self._save_attempt(db, actor_id, body, payload_hash, result)
            return result

    def _save_attempt(self, db, actor_id, body, payload_hash, result):
        db.execute("INSERT INTO attempts VALUES(?,?,?,?,?)", (actor_id, body["idempotency_key"], payload_hash, json.dumps(result, sort_keys=True), now()))

    def deny(self, actor_id, request_id, body):
        require_fields(body, ())
        with self.transaction() as db:
            actor = self.actor(db, actor_id)
            request = self._request(db, actor, request_id, admin=True)
            if actor_id == request["user_id"]:
                raise DomainError(403, "self_review_forbidden", "Another administrator must review your request.")
            if request["status"] == "denied":
                return {"outcome": "denied", "request_id": request_id, "replayed": True}
            if request["status"] == "approved":
                raise DomainError(409, "request_closed", "This request has already been approved.")
            db.execute("UPDATE requests SET status='denied',updated_at=? WHERE id=?", (now(), request_id))
            self._event(db, actor["org_id"], actor_id, request["user_id"], request_id, "access_denied", request["requester_name"] + "’s access request was declined", {})
            self._notify(db, actor["org_id"], request["user_id"], request_id, "Your request was declined", "Your administrator has not assigned a seat. You can discuss access with them or send a new request.")
            return {"outcome": "denied", "request_id": request_id, "replayed": False}

    def read_notifications(self, actor_id, body):
        require_fields(body, ())
        with self.transaction() as db:
            actor = self.actor(db, actor_id)
            db.execute("UPDATE notifications SET read_at=? WHERE user_id=? AND org_id=? AND read_at IS NULL", (now(), actor_id, actor["org_id"]))
            return {"ok": True}

    def demo_info(self):
        with self.connection() as db:
            state = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM demo_state WHERE key!='epoch'")}
            state["personas"] = [dict(r) for r in db.execute("SELECT u.id,u.name,u.role,o.name AS organization FROM users u JOIN organizations o ON o.id=u.org_id WHERE u.id IN ('maya','eli','quinn','robin') ORDER BY u.org_id,u.role DESC,u.name")]
            state["scenarios"] = SCENARIOS
            return state

    def demo_payment(self, body):
        require_fields(body, ("result",), ("result",))
        if body["result"] not in ("success", "failure"):
            raise DomainError(400, "invalid_payment_result", "Choose success or failure for simulated payments.")
        with self.transaction() as db:
            db.execute("UPDATE demo_state SET value=? WHERE key='payment_result'", (body["result"],))
        return {"payment_result": body["result"]}

    def reset(self, body):
        require_fields(body, ("scenario", "confirm"), ("scenario", "confirm"))
        if body["confirm"] != "RESET DEMO":
            raise DomainError(400, "reset_confirmation_required", "Confirm that this resets only the sample demo data.")
        if not isinstance(body["scenario"], str) or body["scenario"] not in SCENARIOS:
            raise DomainError(400, "invalid_scenario", "Choose a known demo scenario.")
        with self.transaction() as db:
            self._seed(db, body["scenario"])
        return {"scenario": body["scenario"], "message": "Sample demo data was reset."}
