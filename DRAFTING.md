# Weekly drafting routine (for Claude)

A scheduled Claude task runs this every **Saturday 11:00 IST**. Harsh reviews and merges the
resulting PR over the weekend; posts go out Monday–Sunday.

## 1. Gather context (read, don't skim)
The facts about Harsh and his apps live in the **private** repo `HarshJaiswal497/content-engine-private`
(never copy its files into this public repo, never quote private details such as project IDs, repo
names, paths or devices in posts).
1. Private repo: `brand/founder.md`, `brand/apps/*.md` (fact sheets — what's shareable and what's off-limits)
   and `brand/apps/*-story.md` (full story bibles; skip anything marked [UNSURE] or [IDEA]).
   Also the private repo's `notes/weekly.md`: Harsh's notes on what happened this week.
2. This repo: `brand/voice.md`, `brand/pillars.md`, `brand/calendar.yml`, `brand/handles.yml`.
3. `inbox/` (public) — screenshots and screen recordings. Everything new since last week is fair game; new screen recordings should become
   faceless Reels/Shorts (`video.kind: recording`).
4. `published/log.jsonl` and the last 2–3 folders in `queue/` — don't repeat a hook, topic or
   format that ran in the last 3 weeks.
5. If the Slipnote / Setalytix repos are attached, skim commits since last week for
   build-in-public material. Only use what the commits actually show.

## 2. Plan the week
Next Monday → Sunday. One post per platform per day at the slot times in `calendar.yml`
(skip days listed as excluded). Balance pillars per `pillars.md`. Per week aim for:
- LinkedIn: 3 text, 3 carousel, 1 image or video.
- Instagram: 4 carousels, 3 Reels (2–3 of the Reels talking-head, rest faceless).
- YouTube: 7 Shorts. Reuse the day's Instagram Reel with `video.kind: same_as` when there is
  one; otherwise make a slide Short (`video.kind: slides`, 4–7 slides, 18–30 s total).

## 3. Write the files
Folder per day: `queue/YYYY-MM-DD/` with `linkedin.yml`, `instagram.yml`, `youtube.yml`.
Schema and examples: `queue/_template.yml` and any recent week.

Hard rules:
- **Facts only from the private repo's `brand/`, this repo's `inbox/`, and nothing else.** Each app's fact sheet lists what's off-limits. No invented numbers, users, quotes or outcomes. If a
  post needs a fact that isn't there (a link, a count), write `TODO: <what's needed>` — validation
  flags it and Harsh fills it in during review.
- Follow `voice.md`. Read every post aloud in your head; cut anything that sounds like a
  LinkedIn template.
- Talking-head posts: `video.script` is 60–110 words, conversational, first line is the hook;
  `video.source` is `inbox/<date>-<slug>.mp4`; `video.hook` is the 3–6 word on-screen hook.
- Slide text: titles ≤ 10 words, bodies ≤ 30 words. Use `*accent*` on 1–3 key words per title.
- Instagram: caption ends with 5–10 specific hashtags. LinkedIn: ≤ 3 hashtags, links in `first_comment`.
- YouTube: `youtube.title` ≤ 60 chars, `youtube.description` 1–3 lines + hashtags, 5–10 tags.

## 4. Ship the drafts
```bash
git checkout -b drafts/<monday-date>
git add queue/ && git commit -m "Drafts for week of <monday-date>"
git push -u origin drafts/<monday-date>
```
GitHub Actions renders all media and opens the review PR automatically. Don't open the PR
yourself and don't push to `main`.

## 5. Report
End with a short summary: the week's themes, which days need a talking-head recording (file
names + scripts), and any TODOs Harsh must fill.
