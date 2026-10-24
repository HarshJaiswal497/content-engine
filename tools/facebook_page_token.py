"""Get a long-lived Facebook Page token so Instagram posts are mirrored to your Page. Run on your laptop:

    python tools/facebook_page_token.py

You need:
  1. Your Meta app's App ID and App secret: developers.facebook.com → your app → App settings → Basic.
     (The main app ID at the top, not the "Instagram app ID".)
  2. A short-lived user token from the Graph API Explorer
     (https://developers.facebook.com/tools/explorer/): choose your app, click "Generate Access Token",
     tick pages_show_list, pages_read_engagement and pages_manage_posts, and allow your Page.

Page tokens created from a long-lived user token don't expire (unless you change your Facebook
password or remove the app), so you normally do this once.
"""
import json
import urllib.parse
import urllib.request
from getpass import getpass

GRAPH = "https://graph.facebook.com/v23.0"


def get(path: str, **params) -> dict:
    url = f"{GRAPH}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Facebook said: {e.read().decode()[:500]}")


app_id = input("Meta App ID: ").strip()
app_secret = getpass("Meta App secret (hidden): ").strip()
short = getpass("Short-lived user token from Graph API Explorer (hidden): ").strip()

long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                client_secret=app_secret, fb_exchange_token=short)["access_token"]
pages = get("me/accounts", fields="id,name,access_token", access_token=long_user).get("data", [])
if not pages:
    raise SystemExit("No Pages found. In the Explorer, make sure you allowed your Page and ticked pages_show_list.")

for i, p in enumerate(pages, 1):
    print(f"{i}. {p['name']} ({p['id']})")
choice = pages[int(input("Which Page? [1]: ").strip() or 1) - 1]

print("\n✅ Add these as GitHub repo secrets (Settings → Secrets and variables → Actions):\n")
print(f"FB_PAGE_ID    = {choice['id']}")
print(f"FB_PAGE_TOKEN = {choice['access_token']}")
print("\nThen clear this window (cls) so the token isn't left on screen.")
