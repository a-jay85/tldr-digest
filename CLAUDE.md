# TLDR Daily Digest

Personal newsletter curator. Fetches TLDR newsletters from Gmail, scores stories for relevance, and drafts a digest email.

## Owner

- **Email:** configured in `config.local.json`
- **Timezone:** America/Los_Angeles (Pacific)
- **Sender:** dan@tldrnewsletter.com

## Architecture

`bin/digest-run` orchestrates the entire pipeline. Only story scoring uses an LLM (`claude -p`); all other steps are deterministic Python scripts. This keeps the LLM context small and prevents timeouts.

**Pipeline:**
1. `python3 gmail_ops.py fetch` — fetch unread TLDR emails → `emails/`, `thread_ids.json`
2. `python3 parse_tldr.py emails/ stories.json` — parse stories, dedup
3. `python3 sync_feedback.py config.json feedback.json` — pull 👍/👎 votes from Google Sheet
4. `python3 filter_seen.py stories.json feedback.json stories_fresh.json` — remove stories seen in last 7 days
5. `claude -p` with `bin/digest-prompt` — score `stories_fresh.json` → `scored_stories.json` (LLM step)
6. `python3 build_email.py scored_stories.json config.json` — generate `digest.html` + `digest_subject.txt`
7. `python3 gmail_ops.py draft` — create Gmail draft
8. `python3 gmail_ops.py archive` — archive fetched threads
9. `python3 update_seen.py scored_stories.json feedback.json` — add digest URLs to seen, prune >14 days
10. `git commit && git push` — persist `feedback.json`

If no fresh stories remain after filtering, steps 5-7 and 9-10 are skipped; threads are still archived.

### Scoring Profile (embedded in `bin/digest-prompt`)

**HIGH (70–100):** AI usage tips/workflows/power-user techniques, how AI leaders think about AI (interviews, thought leadership, strategic perspectives), AI and the job market

**MEDIUM (40–69):** Web dev tooling/React/frontend, product thinking/strategy, developer experience/workflows, notable open source releases

**LOW (20–39):** Funding rounds (only if relevant to HIGH topics), generic company news, government policy (unless it directly affects devs)

**EXCLUDE (<20):** Mobile apps unrelated to dev/AI, crypto/blockchain/Web3, biotech/pharma, sponsored content, pure earnings reports

**Modifiers:** Actionable/practical content: +10 · Matches previous 👍: +10 · Matches previous 👎: −10 · Long reads on LOW topics: −10

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
