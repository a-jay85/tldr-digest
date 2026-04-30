#!/usr/bin/env python3
"""Update feedback.json with today's digest URLs and prune old entries.

Usage:
    python3 update_seen.py scored_stories.json feedback.json

Adds all story URLs from scored_stories.json to the seen array with today's
date, then prunes seen entries older than 14 days.
"""

import json
import sys
from datetime import datetime, timedelta


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <scored_stories.json> <feedback.json>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        scored = json.load(f)

    with open(sys.argv[2]) as f:
        feedback = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

    existing_urls = {s["url"] for s in feedback.get("seen", [])}
    added = 0
    for story in scored:
        url = story.get("url_clean", "")
        if url and url not in existing_urls:
            feedback["seen"].append({
                "url": url,
                "title": story.get("title", ""),
                "date": today,
            })
            existing_urls.add(url)
            added += 1

    before = len(feedback["seen"])
    feedback["seen"] = [
        s for s in feedback["seen"]
        if s.get("date", "1970-01-01") >= cutoff
    ]
    pruned = before - len(feedback["seen"])

    with open(sys.argv[2], "w") as f:
        json.dump(feedback, f, indent=2)
        f.write("\n")

    print(f"Updated seen: +{added} new, -{pruned} pruned, {len(feedback['seen'])} total.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
