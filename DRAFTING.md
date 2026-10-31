# Weekly drafting routine (for Claude)

A scheduled Claude task runs this every **Saturday 11:00 IST**. Harsh reviews and merges the
resulting PR over the weekend; posts go out Monday–Sunday.

## 1. Gather context (read, don't skim)
The facts about Harsh and his apps live in the **private** repo `HarshJaiswal497/content-engine-private`
(never copy its files into this public repo, never quote private details such as project IDs, repo
names, paths or devices in posts).
1. Private repo: `brand/founder.md`, `brand/apps/*.md` (fact sheets — what's shareable and what's off-limits)
   and `brand/apps/*-story.md` (full story bibles; skip anything marked [UNSURE] or [IDEA]).
   Also the private repo's `notes/weekly.md`: Harsh's notes on what happened this week. **This week's news leads:** anything he lists there as new (shipped, fixed, decided, learned) should anchor the build-in-public and feature-spotlight posts of the coming week, ahead of older story-bible material. Use the story bibles to fill the remaining slots and to give background. Notes are facts, but anything marked [UNSURE]/[IDEA] or "don't share" is still off-limits.
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
- Instagram: **a Reel every day (7)** in `instagram-reel.yml` at the `instagram_reel` slot, plus 4
  carousels in `instagram.yml` at the `instagram` slot (so four days have two Instagram posts, three
  days have only the Reel). Of the 7 Reels, 2–3 are talking-head and the rest faceless. Instagram
  posts get few views, so Reels are the growth lever.
- YouTube: 7 Shorts, one per day. Reuse the day's Reel: `video.kind: same_as` with
  `video.post: instagram-reel`.
- Every slide video gets a voiceover: give each slide a `say:` line (one or two short spoken
  sentences, first person as Harsh, conversational, numbers written as words, no hashtags or
  emoji). Line one is the hook. The last line is a platform-neutral CTA ("try it free at
  app.setalytix.in" / "the waitlist link is on my profile"), never "link in description" or
  "link in bio", because Reels reuse the Short. Set `video.tone`: upbeat (Setalytix tips),
  story (Slipnote build moments) or calm. Same rules as captions: no pricing, legal or competitors.

## 3. Write the files
Folder per day: `queue/YYYY-MM-DD/` with `linkedin.yml`, `instagram-reel.yml`, `youtube.yml`, and `instagram.yml` (the carousel) on the four carousel days.
Schema and examples: `queue/_template.yml` and any recent week.

Hard rules:
- **Facts only from the private repo's `brand/` and `notes/weekly.md`, this repo's `inbox/`, and nothing else.** Each app's fact sheet lists what's off-limits. No invented numbers, users, quotes or outcomes. If a
  post needs a fact that isn't there (a link, a count), write `TODO: <what's needed>` — validation
  flags it and Harsh fills it in during review.
- Follow `voice.md`. Read every post aloud in your head; cut anything that sounds like a
  LinkedIn template.
- Talking-head posts: `video.script` is 60–110 words, conversational, first line is the hook;
  `video.source` is `inbox/<date>-<slug>.mp4`; `video.hook` is the 3–6 word on-screen hook.
- Slide text: titles ≤ 10 words, bodies ≤ 30 words. Use `*accent*` on 1–3 key words per title.
- Instagram: caption ends with 5–10 specific hashtags. LinkedIn: ≤ 3 hashtags, links in `first_comment`.
- Money talk (cleared by Harsh, 31 Oct): you may say some Slipnote themes are premium and that there will be free
  trials and a subscription, but only together with "plenty is free and free stays free". Never write a price
  (no monthly or yearly amount, no currency figure) and never mention ads. Test counts, the Slipnote waitlist link and
  app.setalytix.in may be used. Fact sheets say exactly what else is cleared or off-limits.
- YouTube is posted by Harsh by hand: one GitHub issue per week lists every Short with its schedule time,
  title, description and tags, so write each `youtube.title` and `youtube.description` ready to paste.
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
