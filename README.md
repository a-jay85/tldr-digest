# TLDR Daily Digest

Personal newsletter curator that fetches [TLDR](https://tldr.tech/) newsletters from Gmail, scores stories for relevance using Claude, and drafts a curated digest email.

## How it works

`bin/digest-run` orchestrates a 10-step pipeline. Only story scoring uses an LLM (`claude -p`); everything else is deterministic Python.

```
Fetch emails → Parse stories → Sync feedback → Filter seen
    → Score with LLM → Build HTML email → Create Gmail draft
    → Archive threads → Update seen URLs → Git push
```

If no fresh stories remain after filtering, scoring and drafting are skipped; threads are still archived.

## Scoring

Stories are scored 0-100 based on a profile embedded in `bin/digest-prompt`:

| Range | Topics |
|-------|--------|
| **70-100** | AI workflows/tips, AI leadership perspectives, AI and jobs |
| **40-69** | Web dev/React/frontend, product strategy, developer experience, open source |
| **20-39** | Funding rounds (if AI-adjacent), generic company news |
| **<20** | Crypto, biotech, sponsored content, pure earnings (excluded) |

Scores are modified by user feedback: stories matching previous thumbs-up get +10, thumbs-down get -10.

## Feedback loop

Each digest email includes thumbs-up/thumbs-down links per story. Votes are recorded in a Google Sheet via Apps Script (`feedback_webapp.gs`) and synced into `feedback.json` to influence future scoring.

## Setup

### Prerequisites

- Python 3
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude -p` for scoring)
- Gmail API credentials (`credentials.json`)

### Install

```bash
pip install -r requirements.txt
```

### Configure

1. Place Gmail OAuth `credentials.json` in the repo root (see [Gmail API quickstart](https://developers.google.com/gmail/api/quickstart/python))
2. Run `python3 gmail_ops.py fetch` once to complete OAuth and generate `token.json`
3. Edit `config.json` with your email and webapp URL

### Run

```bash
bin/digest-run
```

The runner is designed to be triggered by launchd at 09:00 on weekdays:

```bash
launchctl start com.tldr-digest.daily
```

## Project structure

```
bin/
  digest-run          # Main pipeline orchestrator (bash)
  digest-prompt       # LLM prompt template for scoring

gmail_ops.py          # Fetch, draft, and archive Gmail operations
parse_tldr.py         # Parse TLDR newsletter HTML into stories
filter_seen.py        # Remove recently seen stories
build_email.py        # Generate digest HTML email
update_seen.py        # Track which URLs have been sent
sync_feedback.py      # Pull votes from Google Sheet

feedback_webapp.gs    # Apps Script: receives vote clicks
auto_send_digest.gs   # Apps Script: auto-send the draft

config.json           # Runtime config (email, webapp URL)
feedback.json         # Persistent feedback + seen URL state
```
