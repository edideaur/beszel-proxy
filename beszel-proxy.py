#!/usr/bin/env python3
import json
import os
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

BESZEL_HOST = os.environ.get("BESZEL_HOST", "localhost:8090")
BESZEL_EMAIL = os.environ["BESZEL_EMAIL"]
BESZEL_PASSWORD = os.environ["BESZEL_PASSWORD"]
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "6767"))
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*.prigoana.com")

BASE_URL = f"http://{BESZEL_HOST}"


def allowed_origin(origin):
    if not origin:
        return None
    if CORS_ORIGIN.startswith("*."):
        domain = CORS_ORIGIN[2:]
        if origin.endswith(f".{domain}") or origin == f"https://{domain}":
            return origin
    elif origin == CORS_ORIGIN:
        return origin
    return None

_token = None
_token_expiry = 0


def get_token():
    global _token, _token_expiry

    if _token and time.time() < _token_expiry:
        return _token

    for collection in ("_superusers", "users"):
        req = urllib.request.Request(
            f"{BASE_URL}/api/collections/{collection}/auth-with-password",
            data=json.dumps({"identity": BESZEL_EMAIL, "password": BESZEL_PASSWORD}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.load(res)
                _token = data["token"]
                _token_expiry = time.time() + 3600  # re-auth after 1 hour
                return _token
        except urllib.error.HTTPError:
            continue

    raise RuntimeError("Authentication failed against all collections")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def send_cors(self):
        origin = self.headers.get("Origin", "")
        allowed = allowed_origin(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return

        try:
            token = get_token()
        except RuntimeError as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.send_cors()
            self.end_headers()
            self.wfile.write(str(e).encode())
            return

        url = (
            f"{BASE_URL}/api/collections/systems/records"
            "?page=1&perPage=500&skipTotal=1&sort=%2Bname"
            "&fields=id%2Cname%2Chost%2Cport%2Cinfo%2Cstatus"
        )
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                body = res.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", LISTEN_PORT), Handler)
    print(f"Listening on 127.0.0.1:{LISTEN_PORT}")
    server.serve_forever()
