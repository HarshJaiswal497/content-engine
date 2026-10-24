# Setup (one time, ~1 hour)

Everything here is free. You'll create the new accounts, connect each platform's official API,
and paste a few tokens into GitHub. Do the steps in order.

---

## 1. GitHub repo (5 min)
1. Create a **public** repo called `content-engine` (empty: no README). Public is needed because
   Instagram fetches images from a public URL, and it gives you unlimited free Actions minutes.
   Drafts are visible in the PR before they post; tokens stay secret.
2. Tell Claude the repo name. Claude pushes this code to `main` and week 1's drafts to a
   `drafts/` branch.
3. Repo → **Settings → Actions → General**:
   - *Workflow permissions* → **Read and write permissions**
   - Tick **Allow GitHub Actions to create and approve pull requests**
4. **Settings → Pages** → *Source*: Deploy from a branch → `main` / `/docs` → Save. The Slipnote
   waitlist page goes live at `https://<you>.github.io/content-engine/slipnote/`.
5. Install the **GitHub mobile app** and turn on notifications for this repo (issues + PRs).
   That's your approval inbox.

## 2. Fill in your details (10 min)
- Repo secret `BLOCKED_TERMS`: comma-separated names that must never appear in posts (the competitor
  apps). Copy the list from `blocked-terms.txt` in the private repo. It's a secret so the names aren't public.
- `brand/handles.yml`: your handle and links.
- **Slipnote waitlist form:** [forms.google.com](https://forms.google.com) → blank form "Slipnote waitlist" with
  two questions: *Email* (required) and *Who would you send notes to?* (optional: partner / friends / family).
  Settings → turn off sign-in requirement. Copy the share link, paste it as `FORM_URL` at the bottom of
  `docs/slipnote/index.html` (add your Instagram/LinkedIn links there too). Sign-ups land in the form's
  Responses tab (or a linked Google Sheet).
- `brand/apps/slipnote.md` and `setalytix.md`: the **Status** sections (launch status, links,
  numbers you're happy to share). Content only uses what's written there.

## 3. LinkedIn (15 min)
LinkedIn requires a Company Page for any developer app. A **Slipnote** page doubles as the app's
home on LinkedIn.
1. linkedin.com → *For Business* → **Create a Company Page** → "Slipnote" (logo optional).
2. [developer.linkedin.com](https://developer.linkedin.com) → **Create app** → name it
   "content-engine", link the Slipnote page, upload any logo → Create. Verify the page when asked.
3. **Products** tab → request **Share on LinkedIn** and **Sign In with LinkedIn using OpenID
   Connect** (both approve instantly).
4. **Auth** tab → *Authorized redirect URLs* → add `http://localhost:8765/callback`.
   Note the **Client ID** and **Client Secret**.
5. On your laptop (Windows is fine, Python 3.9+):
   ```
   git clone https://github.com/<you>/content-engine && cd content-engine
   python tools/auth_linkedin.py
   ```
   Log in, approve, and it prints four values.
6. Repo → **Settings → Secrets and variables → Actions → New repository secret**, one each:
   `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`.

The token lasts ~60 days. A GitHub issue reminds you 10 days before; re-run step 5 (2 min).

## 4. Instagram (20 min)
1. Create a new Instagram account (use the same handle as YouTube if you can).
   **Settings → Account type and tools → Switch to professional account → Creator** (category:
   *Software* or *Digital creator*). Add a profile photo and bio.
2. Create a Facebook account if you don't have one (Meta's developer portal needs it), then go to
   [developers.facebook.com](https://developers.facebook.com) → *Get started* → verify.
3. **Create app** → use case **"Manage messaging & content on Instagram"** → app type *Business*
   → name "content-engine".
4. In the app: **Instagram → API setup with Instagram login** →
   *1. Generate access tokens* → **Add account** → log in with the new Instagram account and allow
   the permissions (`instagram_business_basic`, `instagram_business_content_publish`, comments).
   You'll see the account's **Instagram user ID** and a **Generate token** button.
5. Add repo secrets: `IG_ACCESS_TOKEN` (the generated token) and `IG_USER_ID`.

The app can stay in *Development* mode: it only posts to your own account. The token lasts 60
days and is refreshed every Monday automatically once step 6 is done.

## 4b. Facebook Page (optional, 10 min): every Instagram post is also posted to your Page
1. Your Page must be linked to the Instagram account (Page → Settings → Linked accounts → Instagram).
2. developers.facebook.com → your app → **Add use cases** → **"Manage everything on your Page"** → Add.
   No review needed: you're the app's admin and the Page's admin.
3. Open the **Graph API Explorer** (developers.facebook.com/tools/explorer): pick your app, then
   **Generate Access Token** with `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   and allow your Page. Copy the token.
4. App settings → Basic: note the **App ID** and **App secret** (the main ones, not the Instagram ones).
5. On your laptop: `python tools/facebook_page_token.py` and paste the three values when asked.
6. Add repo secrets `FB_PAGE_ID` and `FB_PAGE_TOKEN`. The Page token doesn't expire; a weekly
   check opens an issue if it ever stops working.

## 5. YouTube (5 min now, optional audit later)
1. Create the channel: youtube.com → profile icon → **Create a channel** (same name/handle as
   Instagram). Add a picture and description.
2. That's it for now. The repo variable `YOUTUBE_MODE` defaults to `handoff`: at each Short's
   time you get a GitHub issue with the video and copy-paste metadata, and upload from the
   YouTube app in ~30 seconds.

**Why not fully automatic?** YouTube forces videos uploaded through any unaudited API project
(including self-hosted tools) to stay private. To lift that, later:
1. [console.cloud.google.com](https://console.cloud.google.com) → new project → enable
   **YouTube Data API v3** → OAuth consent screen (External, add the `youtube.upload` scope,
   **publish to production**) → Credentials → OAuth client ID (*Web application*, redirect
   `http://localhost:8765/callback`).
2. Submit the **YouTube API Services audit** form (search "YouTube API Services - Audit and Quota
   Extension Form"). Describe it honestly: a personal tool that uploads your own Shorts to your
   own channel. Approval isn't guaranteed and can take weeks.
3. Once approved: `python tools/auth_youtube.py`, add secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
   `YT_REFRESH_TOKEN`, and set the repo **variable** `YOUTUBE_MODE` = `api`.

## 6. Auto-refresh for the Instagram token (5 min)
1. GitHub → your profile → **Settings → Developer settings → Fine-grained tokens → Generate**.
   Repository access: only `content-engine`. Permissions: **Secrets → Read and write**.
   Expiry: 1 year (set a calendar reminder).
2. Add it as repo secret `SECRETS_PAT`.

## 7. Test it (5 min)
1. Repo → **Actions** → enable workflows if prompted.
2. **Publish due posts → Run workflow → tick Dry run**. The log should list due posts with
   `[dry-run]` and no errors.
3. **Keep tokens fresh → Run workflow**. Should say the Instagram token was refreshed and the
   LinkedIn token is valid.

## 8. Weekly drafting
Claude sets up a scheduled task (Saturdays 11:00 IST) that follows `DRAFTING.md` and pushes
the week's drafts. You get a PR notification; merge it to approve.

---

### Troubleshooting
| Symptom | Fix |
|---|---|
| Issue "Couldn't publish …" mentioning 401 | Token expired: redo the platform's token step. |
| LinkedIn error about version | Set repo variable `LINKEDIN_VERSION` to a recent `YYYYMM` (e.g. last month). |
| Instagram "media not ready" / 9007 | Usually transient; it retries up to 3 times. |
| PR not created for drafts | Step 1.3 permissions; then re-run the *Render & review drafts* workflow. |
| Scheduled runs a few minutes late | Normal for GitHub's scheduler. |
