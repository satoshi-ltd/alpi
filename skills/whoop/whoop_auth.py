#!/usr/bin/env python3
"""
Mini app para autenticación con WHOOP OAuth 2.0.
Guarda el token en ~/.alf/secrets/whoop.json
"""

import os
import json
import webbrowser
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import requests

# Config
CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
REDIRECT_URL = "http://localhost:8080/callback"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
SCOPES = "read:cycles read:sleep read:recovery offline"

SECRETS_DIR = os.path.expanduser("~/.alf/secrets")
SECRETS_FILE = os.path.join(SECRETS_DIR, "whoop.json")

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        query = parse_qs(parsed.query)
        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]

        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: no code received")
            return

        # Exchange code for token
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URL,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if resp.status_code != 200:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Token exchange failed: {resp.text}".encode())
            return

        token_data = resp.json()
        os.makedirs(SECRETS_DIR, exist_ok=True)
        with open(SECRETS_FILE, "w") as f:
            json.dump(token_data, f, indent=2)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Token saved. You can close this window.")

    def log_message(self, format, *args):
        pass  # Silenciar logs

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: WHOOP_CLIENT_ID y WHOOP_CLIENT_SECRET deben estar en el environment")
        print("Ejemplo:")
        print('  export WHOOP_CLIENT_ID="your_id"')
        print('  export WHOOP_CLIENT_SECRET="your_secret"')
        return

    # Start local server
    PORT = 8080
    server = http.server.HTTPServer(("localhost", PORT), CallbackHandler)
    print(f"Escuchando en http://localhost:{PORT}")

    # Build auth URL
    auth_url = f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URL}&scope={SCOPES}&state=alf_whoop"
    print(f"\nAbre esta URL en tu navegador:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Serve for 60 seconds max
    server.timeout = 60
    server.handle_request()
    print("Fin del proceso. Verifica ~/.alf/secrets/whoop.json")

if __name__ == "__main__":
    main()
