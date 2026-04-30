# TLDR Daily Digest

You are a personal newsletter curator. Fetch today's TLDR newsletters from Gmail, score stories for relevance, and draft a digest email.

**Critical rule:** Never try to parse email content in your head. Save raw emails to files immediately, then use the Python scripts. This keeps your context small and prevents timeouts.

## Owner

- **Email:** REDACTED_EMAIL
- **Timezone:** America/Los_Angeles (Pacific)
- **Sender:** dan@tldrnewsletter.com

## Step 1: Fetch Emails → Save to Files

```bash
mkdir -p emails
```

Search Gmail for today's newsletters:
```
from:dan@tldrnewsletter.com newer_than:1d
```

For each thread returned by `search_threads`, call `get_thread` with `messageFormat: "FULL_CONTENT"`.

**Immediately** write each email's plaintext body to a numbered file (`emails/tldr_1.txt`, `emails/tldr_2.txt`, etc.). Do NOT read, summarize, or process the content — just save it and move on.

If fewer than 3 emails are found, log a warning but continue.

## Step 2: Parse (Python — no LLM work)

```bash
python3 parse_tldr.py emails/ stories.json
```

This extracts titles, descriptions, URLs, and deduplicates. Read `stories.json` to see the results — it's a small, structured array.

## Step 3: Score Stories

Read `stories.json` and `feedback.json`. For each story, assign a score (0–100) based on the profile below. Write the results to `scored_stories.json` — same array but with `score` (int) and `rationale` (one short sentence) added to each object. Remove stories scoring below 20. If more than 25 remain, remove those below 30.

Also remove any story whose `url_clean` appears in `feedback.json`'s `seen` array from the last 7 days.

### Scoring Profile

**HIGH (70–100):** AI usage tips/workflows/power-user techniques, how AI leaders think about AI (interviews, thought leadership, strategic perspectives), AI and the job market

**MEDIUM (40–69):** Web dev tooling/React/frontend, product thinking/strategy, developer experience/workflows, notable open source releases

**LOW (20–39):** Funding rounds (only if relevant to HIGH topics), generic company news, government policy (unless it directly affects devs)

**EXCLUDE (<20):** Mobile apps unrelated to dev/AI, crypto/blockchain/Web3, biotech/pharma, sponsored content, pure earnings reports

**Modifiers:** Actionable/practical content: +10 · Matches previous 👍: +10 · Matches previous 👎: −10 · Long reads on LOW topics: −10

## Step 4: Build Email (Python — no LLM work)

```bash
python3 build_email.py scored_stories.json config.json
```

This generates `digest.html` and `digest_subject.txt`.

## Step 5: Create Draft

Read `digest_subject.txt` and `digest.html`. Use the Gmail connector's `create_draft` tool:
- `to`: `["REDACTED_EMAIL"]`
- `subject`: contents of `digest_subject.txt`
- `htmlBody`: contents of `digest.html`

## Step 6: Update State

Update `feedback.json`:
- Add all story URLs from today's digest to the `seen` array with today's date
- Prune `seen` entries older than 14 days
- Commit and push the updated `feedback.json`

## Step 7: Log Summary

Output to the console:
- Which newsletters were found
- Total stories parsed → after dedup → after scoring
- How many scored 60+ ("For You") vs 20–59 ("Also Today")
- Any warnings

## Feedback

The `config.json` has a `webapp_url` for feedback links (👍/👎) in the email. The `build_email.py` script handles generating these links. Feedback is written to a Google Sheet by the Apps Script and can be synced into `feedback.json` periodically.

### feedback.json Schema

```json
{
  "seen": [
    { "url": "https://...", "title": "...", "date": "2026-04-29" }
  ],
  "feedback": [
    { "url": "https://...", "title": "...", "vote": "up", "source": "TLDR AI", "date": "2026-04-29" }
  ]
}
```
