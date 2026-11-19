# ==============================================================================
# Program: server.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 19, 2026
# Purpose: Loopback HTTP API server and static asset delivery daemon for Access Lab.
#          Implements a secure multi-threaded BaseHTTPRequestHandler microservice
#          strictly constrained to loopback socket interfaces, enforcing origin
#          isolation, Host header matching, CSP security policies, and 16KB payload
#          ceilings while routing RESTful JSON transactions to the domain Store engine.
# ==============================================================================
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

# Root directory path anchor of the application
ROOT = Path(__file__).resolve().parent.parent
# Filesystem path to client assets (HTML, CSS, JS, SVG)
STATIC = ROOT / "app" / "static"
# Whitelist of permissible public Markdown documentation files
DOC_NAMES = {"brief.md", "evidence.md", "decisions.md", "supervision.md", "verification.md", "case-study.md", "walkthrough.md"}


def is_loopback(host: str) -> bool:
    """Verify whether a target hostname or IP address resolves strictly to local loopback.
    
    Args:
        host: Hostname string or IP address representation.
        
    Returns:
        bool: True if host is 'localhost' or within 127.0.0.0/8 or ::1, False otherwise.
    """
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# HTTP request dispatcher mapping REST endpoints to domain store operations
class Handler(BaseHTTPRequestHandler):
    """Custom request handler processing loopback REST API transactions and static files."""
    server_version = "AccessLab/1.0"

    def log_message(self, format, *args):
        """Format and emit timestamped server log lines to standard error stream."""
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))

    @property
    def store(self) -> Store:
        """Convenience property accessing the shared domain persistence Store instance."""
        return self.server.store

    def _headers(self, status: int, content_type: str, length: int):
        """Inject standardized response headers including security restrictions and cache control.
        
        Args:
            status: HTTP response code.
            content_type: MIME type with character set declaration.
            length: Content-Length payload byte count.
        """
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # Enforce strict Content Security Policy forbidding foreign script execution and framing
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()

    def _json(self, status: int, body: dict):
        """Serialize a Python dictionary to UTF-8 encoded JSON and write to connection stream.
        
        Args:
            status: HTTP response code.
            body: Serializable dictionary payload.
        """
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def _guard(self):
        """Assert strict security preconditions to block DNS rebinding and cross-origin attacks.
        
        Verifies that:
        1. Host header matches a loopback IP or localhost and matches the server listen port.
        2. Client socket remote address is a verified loopback IP.
        3. Origin header (if present) exactly matches the local Host.
        4. Sec-Fetch-Site is not flagged as 'cross-site'.
        
        Raises:
            DomainError(403): If any perimeter invariant fails.
        """
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

    def _body(self) -> dict:
        """Inspect, read, and parse incoming HTTP JSON request body with defensive limits.
        
        Enforces:
        - Content-Type must strictly be application/json.
        - Prohibits chunked transfer encoding.
        - Size bounds between 1 byte and 16,384 bytes (16 KB limit).
        
        Returns:
            dict: Parsed JSON object.
            
        Raises:
            DomainError(400/415): On invalid headers, sizes, or unparseable JSON payloads.
        """
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
        """Handle incoming HTTP GET requests by routing through the security guard."""
        self._handle(False)

    def do_POST(self):
        """Handle incoming HTTP POST requests by parsing payload and executing mutations."""
        self._handle(True)

    def _handle(self, post: bool):
        """Central dispatch pipeline for GET and POST HTTP requests.
        
        Coordinates security boundary validation, actor extraction from headers,
        route matching, transactional store execution, and unified error mapping.
        """
        try:
            self._guard()
            path = urlsplit(self.path).path
            actor = self.headers.get("X-Demo-User")
            
            if post:
                body = self._body()
                # Demonstration environment controls operate outside regular persona boundaries
                if path == "/api/demo/reset":
                    result = self.store.reset(body)
                elif path == "/api/demo/payment":
                    result = self.store.demo_payment(body)
                elif path == "/api/requests":
                    result = self.store.create_request(actor, body)
                elif path == "/api/notifications/read":
                    result = self.store.read_notifications(actor, body)
                elif match := re.fullmatch(r"/api/requests/([1-9][0-9]*)/(approve|deny)", path):
                    # Route approval or denial based on dynamic sub-path parameter
                    action = self.store.approve if match[2] == "approve" else self.store.deny
                    result = action(actor, int(match[1]), body)
                else:
                    raise DomainError(404, "not_found", "This action does not exist.")
                self._json(201 if result.get("created") else 200, result)
            elif path == "/api/workspace":
                # Aggregate user profile, seat metrics, and activity history
                self._json(200, self.store.workspace(actor))
            elif path == "/api/shared-workspace":
                # Entitlement-gated shared review workspace state
                self._json(200, self.store.shared_workspace(actor))
            elif path == "/api/demo/info":
                # Global demonstration metadata and scenario options
                self._json(200, self.store.demo_info())
            elif match := re.fullmatch(r"/api/requests/([1-9][0-9]*)(/quote)?", path):
                # Fetch either cost quote fingerprint or request status summary
                action = self.store.quote if match[2] else self.store.request_detail
                self._json(200, action(actor, int(match[1])))
            elif path.startswith("/api/"):
                raise DomainError(404, "not_found", "This endpoint does not exist.")
            else:
                # Deliver static web assets or whitelisted documentation files
                self._static(path)
        except DomainError as exc:
            # Map domain business exceptions directly to structured JSON responses
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except (sqlite3.Error, OSError, ValueError) as exc:
            # Log unexpected operational failures and return a resilient generic error
            self.log_error("Request failed: %s", type(exc).__name__)
            self._json(500, {"error": {"code": "server_error", "message": "The local app could not complete this action. Your last saved state is preserved; refresh and try again."}})

    def _static(self, path: str):
        """Safely resolve, sanitize, and deliver local static assets and Markdown documentation.
        
        Guarantees path containment within the STATIC or DOCS directories to avert directory traversal.
        """
        path = unquote(path)
        if path.startswith("/docs/"):
            name = path.removeprefix("/docs/")
            if name not in DOC_NAMES:
                raise DomainError(404, "not_found", "This document is not available.")
            file = ROOT / "docs" / name
            content_type = "text/plain; charset=utf-8"
        else:
            file = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
            # Verify resolved target remains strictly within the STATIC root directory
            if not file.resolve().is_relative_to(STATIC.resolve()):
                raise DomainError(404, "not_found", "This file is not available.")
            content_type = (mimetypes.guess_type(file)[0] or "application/octet-stream") + "; charset=utf-8"
            
        if not file.is_file():
            raise DomainError(404, "not_found", "This file is not available.")
            
        raw = file.read_bytes()
        self._headers(200, content_type, len(raw))
        self.wfile.write(raw)


def make_server(host="127.0.0.1", port=8765, db_path=None) -> ThreadingHTTPServer:
    """Instantiate and configure multi-threaded HTTP server bound to loopback.
    
    Args:
        host: Loopback IP address or hostname.
        port: Integer TCP listen port.
        db_path: Optional custom path to SQLite database.
        
    Returns:
        ThreadingHTTPServer: Bound and configured HTTP server daemon.
    """
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
    """CLI application entrypoint: parse runtime arguments and start HTTP loopback listener."""
    parser = argparse.ArgumentParser(description="Access Lab — independent loopback-only portfolio demo")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="TCP listen port (default: 8765)")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "access-lab.sqlite3", help="Target SQLite file path")
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
