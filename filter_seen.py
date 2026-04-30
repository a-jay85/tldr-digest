#!/usr/bin/env python3
"""Pre-filter stories against recently seen URLs.

Usage:
    python3 filter_seen.py stories.json feedback.json stories_fresh.json

Removes stories whose url_clean appears in feedback.json's seen array
from the last 7 days. Writes the remaining stories to stories_fresh.json.
"""

import json
import sys
from datetime import datetime, timedelta


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <stories.json> <feedback.json> <stories_fresh.json>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        stories = json.load(f)

    with open(sys.argv[2]) as f:
        feedback = json.load(f)

    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    seen_urls = {
        s["url"] for s in feedback.get("seen", [])
        if s.get("date", "1970-01-01") >= cutoff
    }

    fresh = [s for s in stories if s["url_clean"] not in seen_urls]

    with open(sys.argv[3], "w") as f:
        json.dump(fresh, f, indent=2)
        f.write("\n")

    print(f"Filtered: {len(stories)} total, {len(stories) - len(fresh)} seen, {len(fresh)} fresh.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
