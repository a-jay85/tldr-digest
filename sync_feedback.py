#!/usr/bin/env python3
"""Sync feedback from the Apps Script endpoint into feedback.json.

Usage:
    python3 sync_feedback.py config.json feedback.json

Fetches all feedback rows via ?action=export, merges new entries into
feedback.json's "feedback" array (deduped by url+vote), and writes back.
"""

import json
import sys
import urllib.request
from datetime import datetime


def fetch_feedback(webapp_url: str) -> list[dict]:
    url = f"{webapp_url}?action=export"
    req = urllib.request.Request(url, headers={"User-Agent": "sync_feedback/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read().decode()
        if "text/html" in content_type or body.lstrip().startswith("<!"):
            print("Warning: webapp returned HTML (likely a login page). "
                  "Redeploy the Apps Script with access set to 'Anyone'.",
                  file=sys.stderr)
            return []
        return json.loads(body)


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <config.json> <feedback.json>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        config = json.load(f)

    webapp_url = config.get("webapp_url", "")
    if not webapp_url:
        print("No webapp_url in config.json — nothing to sync.", file=sys.stderr)
        sys.exit(0)

    with open(sys.argv[2]) as f:
        local = json.load(f)

    existing = {(e["url"], e["vote"]) for e in local.get("feedback", [])}

    rows = fetch_feedback(webapp_url)
    added = 0
    for row in rows:
        url = row.get("URL", "")
        vote = row.get("Vote", "")
        if not url or not vote:
            continue
        if (url, vote) in existing:
            continue

        ts = row.get("Timestamp", "")
        try:
            date = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date = datetime.now().strftime("%Y-%m-%d")

        local["feedback"].append({
            "url": url,
            "title": row.get("Title", ""),
            "vote": vote,
            "source": row.get("Source Newsletter", ""),
            "date": date,
        })
        existing.add((url, vote))
        added += 1

    with open(sys.argv[2], "w") as f:
        json.dump(local, f, indent=2)
        f.write("\n")

    total = len(local["feedback"])
    print(f"Synced: {added} new, {total} total feedback entries.", file=sys.stderr)


if __name__ == "__main__":
    main()
