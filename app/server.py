"""Loopback-only HTTP interface. Run: python3 -m app.server."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
from pathlib import Path
import re
import socket
import sqlite3
import sys
from urllib.parse import urlsplit, unquote

if __package__:
    from .domain import DomainError, Store
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.domain import DomainError, Store

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
DOC_NAMES = {"brief.md", "evidence.md", "decisions.md", "supervision.md", "verification.md", "case-study.md", "walkthrough.md"}


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "AccessLab/1.0"

    def log_message(self, format, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))

    @property
    def store(self):
        return self.server.store

    def _headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()

    def _json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def _guard(self):
        try:
            host = self.headers.get("Host", "")
            parsed = urlsplit("http://" + host)
            if not host or not is_loopback(parsed.hostname or "") or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise ValueError
            if parsed.port != self.server.server_port:
                raise ValueError
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                raise ValueError
        except (ValueError, TypeError):
            raise DomainError(403, "local_only", "Access Lab accepts loopback requests to its local port only.")
        origin = self.headers.get("Origin")
        if (origin and origin != "http://" + host) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise DomainError(403, "origin_rejected", "Open Access Lab directly on its local address.")

    def _body(self):
        if self.headers.get_content_type() != "application/json":
            raise DomainError(415, "json_required", "Use Content-Type: application/json.")
        if self.headers.get("Transfer-Encoding"):
            raise DomainError(400, "invalid_body", "Chunked request bodies are not supported.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError
        except ValueError:
            raise DomainError(400, "invalid_body", "Send a JSON body smaller than 16 KB.")
        try:
            body = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError):
            raise DomainError(400, "invalid_json", "The request body is not valid JSON.")
        if not isinstance(body, dict):
            raise DomainError(400, "invalid_body", "Send a JSON object.")
        return body

    def do_GET(self):
        self._handle(False)

    def do_POST(self):
        self._handle(True)

    def _handle(self, post):
        try:
            self._guard()
            path = urlsplit(self.path).path
            actor = self.headers.get("X-Demo-User")
            if post:
                body = self._body()
                # Demo controls are deliberately outside persona permissions.
                # They reset/configure fictitious data; they are not admin APIs.
                if path == "/api/demo/reset":
                    result = self.store.reset(body)
                elif path == "/api/demo/payment":
                    result = self.store.demo_payment(body)
                elif path == "/api/requests":
                    result = self.store.create_request(actor, body)
                elif path == "/api/notifications/read":
                    result = self.store.read_notifications(actor, body)
                elif match := re.fullmatch(r"/api/requests/([1-9][0-9]*)/(approve|deny)", path):
                    action = self.store.approve if match[2] == "approve" else self.store.deny
                    result = action(actor, int(match[1]), body)
                else:
                    raise DomainError(404, "not_found", "This action does not exist.")
                self._json(201 if result.get("created") else 200, result)
            elif path == "/api/workspace":
                self._json(200, self.store.workspace(actor))
            elif path == "/api/shared-workspace":
                self._json(200, self.store.shared_workspace(actor))
            elif path == "/api/demo/info":
                self._json(200, self.store.demo_info())
            elif match := re.fullmatch(r"/api/requests/([1-9][0-9]*)(/quote)?", path):
                action = self.store.quote if match[2] else self.store.request_detail
                self._json(200, action(actor, int(match[1])))
            elif path.startswith("/api/"):
                raise DomainError(404, "not_found", "This endpoint does not exist.")
            else:
                self._static(path)
        except DomainError as exc:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.log_error("Request failed: %s", type(exc).__name__)
            self._json(500, {"error": {"code": "server_error", "message": "The local app could not complete this action. Your last saved state is preserved; refresh and try again."}})

    def _static(self, path):
        path = unquote(path)
        if path.startswith("/docs/"):
            name = path.removeprefix("/docs/")
            if name not in DOC_NAMES:
                raise DomainError(404, "not_found", "This document is not available.")
            file = ROOT / "docs" / name
            content_type = "text/plain; charset=utf-8"
        else:
            file = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
            if not file.resolve().is_relative_to(STATIC.resolve()):
                raise DomainError(404, "not_found", "This file is not available.")
            content_type = (mimetypes.guess_type(file)[0] or "application/octet-stream") + "; charset=utf-8"
        if not file.is_file():
            raise DomainError(404, "not_found", "This file is not available.")
        raw = file.read_bytes()
        self._headers(200, content_type, len(raw))
        self.wfile.write(raw)


def make_server(host="127.0.0.1", port=8765, db_path=None):
    if not is_loopback(host):
        raise ValueError("Access Lab must bind to a loopback address (127.0.0.1, localhost, or ::1).")
    server_type = ThreadingHTTPServer
    if ":" in host:
        class IPv6Server(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        server_type = IPv6Server
    server = server_type((host, port), Handler)
    server.store = Store(db_path or ROOT / "data" / "access-lab.sqlite3")
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description="Access Lab — independent loopback-only portfolio demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "access-lab.sqlite3")
    args = parser.parse_args()
    if not is_loopback(args.host):
        parser.error("--host must be a loopback address; public hosting is outside this demo’s scope")
    server = make_server(args.host, args.port, args.db)
    shown_host = "[" + args.host + "]" if ":" in args.host else args.host
    print(f"Access Lab: http://{shown_host}:{server.server_port}", flush=True)
    print(f"Sample data: {Path(args.db).resolve()}", flush=True)
    print("Local demo identities and simulated payments only. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped Access Lab.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
