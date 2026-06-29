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
7. `python3 send_digest.py config.json` — POST `digest.html`/`digest_subject.txt` to the Apps Script `sendDigest` endpoint, which emails the digest via GmailApp
8. `python3 gmail_ops.py archive` — archive fetched threads
9. `python3 update_seen.py scored_stories.json feedback.json` — add digest URLs to seen, prune >14 days
10. `git commit && git push` — persist `feedback.json`

If no fresh stories remain after filtering, steps 5-7 and 9-10 are skipped; threads are still archived.

### Usage-limit retry

If the LLM scoring step hits a Claude usage/session limit, `digest-run` parses the reset time from the error and schedules a one-shot launchd job (`com.tldr-digest.retry`, `DIGEST_RETRY=1`) to re-run the whole (idempotent) pipeline once the limit clears. The retry run self-removes its launchd job on exit; a `DIGEST_RETRY` guard prevents reschedule loops.

### Apps Script deploy

The web app lives in `apps-script/` and is managed with `clasp`. After editing any `.gs`, run `bin/deploy-appsscript` to push the source and redeploy the live `/exec` deployment in place (deployment id is derived from `apps_script_url`, so the redeploy target always matches what `send_digest.py` POSTs to). No manual editing in the Apps Script IDE.

### Scoring Profile (embedded in `bin/digest-prompt`)

**HIGH (70–100):** AI usage tips/workflows/power-user techniques, how AI leaders think about AI (interviews, thought leadership, strategic perspectives), AI and the job market

**MEDIUM (40–69):** Web dev tooling/React/frontend, product thinking/strategy, developer experience/workflows, notable open source releases

**LOW (20–39):** Funding rounds (only if relevant to HIGH topics), generic company news, government policy (unless it directly affects devs)

**EXCLUDE (<20):** Mobile apps unrelated to dev/AI, crypto/blockchain/Web3, biotech/pharma, sponsored content, pure earnings reports

**Modifiers:** Actionable/practical content: +10 · Matches previous 👍: +10 · Matches previous 👎: −10 · Long reads on LOW topics: −10

## Feedback

The `config.json` has a `webapp_url` (the GitHub Pages redirect) for feedback links (👍/👎) in the email; `build_email.py` generates these GET links. `apps_script_url` is the script's `/exec` deployment, used by `sync_feedback.py` (export votes) and `send_digest.py` (POST the digest to send). Feedback is written to a Google Sheet by the Apps Script and can be synced into `feedback.json` periodically.

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
