"""Get a YouTube refresh token (only needed once your project passes the YouTube API audit
and you switch YOUTUBE_MODE to 'api'). Run on your laptop:

    python tools/auth_youtube.py

Before running: Google Cloud Console → your project → enable "YouTube Data API v3"; OAuth
consent screen → External, publish the app ("In production") so the token doesn't expire
after 7 days; Credentials → OAuth client ID → "Web application" with authorised redirect URI
http://localhost:8765/callback.
"""
from getpass import getpass

from _oauth import REDIRECT, get_code, post_form

client_id = input("Google OAuth Client ID: ").strip()
client_secret = getpass("Google OAuth Client Secret (hidden): ").strip()

code = get_code("https://accounts.google.com/o/oauth2/v2/auth", {
    "client_id": client_id, "scope": "https://www.googleapis.com/auth/youtube.upload",
    "access_type": "offline", "prompt": "consent"})
tok = post_form("https://oauth2.googleapis.com/token", {
    "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
    "client_id": client_id, "client_secret": client_secret})

if "refresh_token" not in tok:
    raise SystemExit("No refresh token returned. Remove the app's access at myaccount.google.com/permissions and retry.")
print("\n✅ Add these as GitHub repo secrets:\n")
print(f"YT_CLIENT_ID     = {client_id}")
print("YT_CLIENT_SECRET = (the secret you just typed)")
print(f"YT_REFRESH_TOKEN = {tok['refresh_token']}")
print("\nThen set the repo variable YOUTUBE_MODE = api")
