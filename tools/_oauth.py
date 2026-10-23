"""Tiny local OAuth helper (stdlib only) shared by auth_linkedin.py and auth_youtube.py."""
from __future__ import annotations

import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT = f"http://localhost:{PORT}/callback"


def get_code(auth_url: str, params: dict) -> str:
    state = secrets.token_urlsafe(16)
    url = auth_url + "?" + urllib.parse.urlencode({**params, "redirect_uri": REDIRECT, "state": state,
                                                    "response_type": "code"})
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Done - you can close this tab and go back to the terminal.</h2>")
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    print(f"\nOpening your browser. If it doesn't open, visit:\n{url}\n")
    webbrowser.open(url)
    server.serve_forever()
    if result.get("state") != state:
        raise SystemExit("State mismatch - try again.")
    if "error" in result:
        raise SystemExit(f"Authorisation failed: {result.get('error')} {result.get('error_description', '')}")
    return result["code"]


def post_form(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())
