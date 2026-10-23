# content-engine

Daily LinkedIn, Instagram and YouTube content about what I build: drafted by Claude,
approved by me, published automatically. Costs ₹0.

```
Sat  Claude drafts next week ──► drafts/<date> branch
         │
         ▼
     GitHub Actions renders slides + videos ──► opens a PR with previews
         │
         ▼
     I review on my phone, edit if needed, MERGE = approve
         │
         ▼
Daily  Actions publishes each post at its slot (LinkedIn 09:15 · YouTube 17:45 · Instagram 19:30 IST)
```

## My weekly routine (~10 min)
1. **Through the week:** jot what I shipped/broke/learned in `notes/weekly.md` in the private repo; drop screenshots and
   screen recordings in `inbox/`.
2. **Saturday:** Claude's drafts PR arrives. Read it, fix anything that isn't true or doesn't sound
   like me, fill any `TODO`, then **merge**.
3. **Talking-head days:** record the script from the PR and upload it to the file name it asks for
   (`inbox/…mp4`). It's captioned and posted automatically. Forget, and you get a reminder issue;
   nothing half-finished is posted.
4. **YouTube (until the API audit is approved):** at 17:45 an issue arrives with the finished Short
   and copy-paste title/description/tags. Upload from the YouTube app, close the issue.

## What's where
| Path | What |
|---|---|
| `brand/` | Voice, pillars, posting slots, handles. App facts and personal details live in the **private** repo `content-engine-private`. |
| `inbox/` | My raw material for the next drafting run. |
| `queue/YYYY-MM-DD/*.yml` | One file per post. Schema: `queue/_template.yml`. |
| `queue/…/assets/` | Rendered slides (videos live in the `media` release to keep git small). |
| `published/log.jsonl` | What was posted, when, and where. |
| `engine/` | Python: validation, rendering (Pillow + ffmpeg + faster-whisper), publishers. |
| `.github/workflows/` | `render.yml` (drafts → PR), `publish.yml` (every 15 min), `tokens.yml` (weekly). |
| `DRAFTING.md` | The instructions Claude follows each week. |

## Changing things
- **Edit or drop a post before it's live:** edit/delete its `.yml` on `main` (or in the PR).
- **Pause everything:** Actions → *Publish due posts* → ⋯ → *Disable workflow*.
- **Change slot times or skip days:** `brand/calendar.yml`.
- **Retry a failed post:** fix the cause, delete that post's last lines in `published/log.jsonl`.
- **Test without posting:** Actions → *Publish due posts* → *Run workflow* → tick *Dry run*.

Local: `pip install -r requirements.txt && python -m engine.render && python -m pytest -q`.

Setup from scratch: [SETUP.md](SETUP.md).
