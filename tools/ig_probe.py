"""One-off: can Instagram fetch a Reel from its public URL? Creates a container and polls it. NEVER publishes."""
import sys, time
import requests
from engine import post as P
from engine.platforms import instagram as ig
from engine.config import ROOT

p = P.load(ROOT / sys.argv[1])
url = ig.reel_url(p)
print("video_url:", url)
cid = ig._container(ig.user_id(), media_type="REELS", video_url=url, caption="probe (not published)")
print("container:", cid)
for _ in range(30):
    d = requests.get(f"{ig._base()}/{cid}", params={"fields": "status_code,status", "access_token": ig._token()}, timeout=30).json()
    print(d, flush=True)
    if d.get("status_code") in {"FINISHED", "ERROR", "EXPIRED"}:
        break
    time.sleep(10)
