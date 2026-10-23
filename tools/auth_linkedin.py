"""Get a LinkedIn access token for posting to your own profile. Run on your laptop:

    python tools/auth_linkedin.py

Before running: in your LinkedIn developer app → Auth tab, add the redirect URL
http://localhost:8765/callback. Products tab: "Share on LinkedIn" and
"Sign In with LinkedIn using OpenID Connect".
"""
from getpass import getpass

from _oauth import REDIRECT, get_code, get_json, post_form

client_id = input("LinkedIn Client ID: ").strip()
client_secret = getpass("LinkedIn Client Secret (hidden): ").strip()

code = get_code("https://www.linkedin.com/oauth/v2/authorization",
                {"client_id": client_id, "scope": "openid profile w_member_social"})
tok = post_form("https://www.linkedin.com/oauth/v2/accessToken", {
    "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
    "client_id": client_id, "client_secret": client_secret})
me = get_json("https://api.linkedin.com/v2/userinfo", tok["access_token"])

print("\n✅ Add these as GitHub repo secrets (Settings → Secrets and variables → Actions):\n")
print(f"LINKEDIN_ACCESS_TOKEN = {tok['access_token']}")
print(f"LINKEDIN_PERSON_URN   = urn:li:person:{me['sub']}")
print(f"LINKEDIN_CLIENT_ID    = {client_id}")
print("LINKEDIN_CLIENT_SECRET = (the secret you just typed)")
print(f"\nToken valid for ~{tok.get('expires_in', 0) // 86400} days. You'll get a GitHub issue before it expires.")
