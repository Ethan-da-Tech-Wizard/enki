# Program: Access Lab - server.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Loopback-only HTTP server that routes the JSON API and static files to the Store and applies local-only request guards.
"""Loopback-only HTTP interface. Run: python3 -m app.server."""

# Imports: standard-library modules for the HTTP server, parsing, and files.
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

# Support both `python3 -m app.server` (package import) and running the file directly
# (adds the project root to the import path first).
if __package__:
    from .domain import DomainError, Store
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.domain import DomainError, Store

# --- Paths and constants ---
# Project root, static web assets folder, and the whitelist of documents that may be served.
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
DOC_NAMES = {"brief.md", "evidence.md", "decisions.md", "supervision.md", "verification.md", "case-study.md", "walkthrough.md"}


def is_loopback(host):
    """Return True only for 'localhost' or a loopback IP address; anything else (including bad text) is False."""
    # Names are not resolved; only the literal 'localhost' is trusted by name.
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    """Request handler: validates each request is local, then dispatches GET/POST to the Store or serves static files."""
    # Server name reported in responses.
    server_version = "AccessLab/1.0"

    def log_message(self, format, *args):
        """Write the access log line to stderr with a timestamp."""
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))

    @property
    def store(self):
        """The shared Store attached to the running server."""
        return self.server.store

    def _headers(self, status, content_type, length):
        """Send the status line and the standard response headers, including no-store caching and a strict Content-Security-Policy."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # Only same-origin scripts, styles, and connections are allowed; framing is forbidden.
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()

    def _json(self, status, body):
        """Serialize `body` as UTF-8 JSON and send it with the given status."""
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def _guard(self):
        """Reject requests that do not target the loopback address and this server's own port,
        or that come from another origin; raises DomainError(403) on failure.
        """
        try:
            # Check the Host header: must be a loopback name, with no credentials, path, query, or fragment.
            host = self.headers.get("Host", "")
            parsed = urlsplit("http://" + host)
            if not host or not is_loopback(parsed.hostname or "") or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise ValueError
            # The port must match the one this server is listening on.
            if parsed.port != self.server.server_port:
                raise ValueError
            # The connecting client must also be on the loopback interface.
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                raise ValueError
        except (ValueError, TypeError):
            raise DomainError(403, "local_only", "Access Lab accepts loopback requests to its local port only.")
        # Block cross-origin and cross-site browser requests.
        origin = self.headers.get("Origin")
        if (origin and origin != "http://" + host) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise DomainError(403, "origin_rejected", "Open Access Lab directly on its local address.")

    def _body(self):
        """Read and validate the JSON request body (JSON content type, no chunking, 1 to 16384 bytes, a JSON object) and return it as a dict."""
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
        """Handle an HTTP GET."""
        self._handle(False)

    def do_POST(self):
        """Handle an HTTP POST."""
        self._handle(True)

    def _handle(self, post):
        """Route one request: guard it, read the demo identity header, call the matching Store method,
        and turn domain or database errors into JSON error responses.
        """
        try:
            self._guard()
            path = urlsplit(self.path).path
            # The demo identity (a persona id) is chosen by the client; it is not a real login.
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
        # Unexpected failures are logged by type only and reported with a generic message.
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.log_error("Request failed: %s", type(exc).__name__)
            self._json(500, {"error": {"code": "server_error", "message": "The local app could not complete this action. Your last saved state is preserved; refresh and try again."}})

    def _static(self, path):
        """Serve a static asset or an allow-listed document, refusing any path that escapes its folder."""
        path = unquote(path)
        if path.startswith("/docs/"):
            name = path.removeprefix("/docs/")
            if name not in DOC_NAMES:
                raise DomainError(404, "not_found", "This document is not available.")
            file = ROOT / "docs" / name
            content_type = "text/plain; charset=utf-8"
        else:
            file = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
            # Path-traversal guard: the resolved file must stay inside the static folder.
            if not file.resolve().is_relative_to(STATIC.resolve()):
                raise DomainError(404, "not_found", "This file is not available.")
            content_type = (mimetypes.guess_type(file)[0] or "application/octet-stream") + "; charset=utf-8"
        if not file.is_file():
            raise DomainError(404, "not_found", "This file is not available.")
        raw = file.read_bytes()
        self._headers(200, content_type, len(raw))
        self.wfile.write(raw)


def make_server(host="127.0.0.1", port=8765, db_path=None):
    """Create (but do not start) the HTTP server bound to a loopback address, with a Store opened on `db_path`."""
    if not is_loopback(host):
        raise ValueError("Access Lab must bind to a loopback address (127.0.0.1, localhost, or ::1).")
    server_type = ThreadingHTTPServer
    # IPv6 addresses need a server class that uses the IPv6 address family.
    if ":" in host:
        class IPv6Server(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        server_type = IPv6Server
    server = server_type((host, port), Handler)
    server.store = Store(db_path or ROOT / "data" / "access-lab.sqlite3")
    server.daemon_threads = True
    return server


def main():
    """Command-line entry point: parse options, start the server, print where it is listening, and serve until Ctrl+C."""
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
