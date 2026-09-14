#!/usr/bin/env python3
"""Build the LLM scoring prompts from fresh stories and recent feedback.

Usage:
    python3 build_prompt.py stories_fresh.json feedback.json prompt_system.txt prompt_user.txt

Writes two files:
  - prompt_system.txt: bin/digest-prompt with recent votes substituted in
  - prompt_user.txt:   a compact numbered list of stories (no URLs)

Stories are referenced by 1-based index; merge_scores.py joins on that index.
Only votes from the last FEEDBACK_DAYS are included so the prompt doesn't
grow forever.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

FEEDBACK_DAYS = 90
TEMPLATE = Path(__file__).resolve().parent / "bin" / "digest-prompt"


def format_story(i: int, s: dict) -> str:
    rt = s.get("read_time", 0)
    length = f"{rt} min" if rt and rt > 0 else "repo"
    desc = " ".join((s.get("description") or "").split())
    return f"{i}. [{s.get('source', '')}, {length}] {s['title']} — {desc}"


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <stories_fresh.json> <feedback.json> "
              f"<prompt_system.txt> <prompt_user.txt>", file=sys.stderr)
        sys.exit(1)

    stories = json.load(open(sys.argv[1]))
    feedback = json.load(open(sys.argv[2])).get("feedback", [])

    cutoff = (datetime.now() - timedelta(days=FEEDBACK_DAYS)).strftime("%Y-%m-%d")
    recent = [v for v in feedback if v.get("date", "1970-01-01") >= cutoff]
    if recent:
        votes = "\n".join(f"  {v['vote'].upper()}: {v['title']} ({v['source']})" for v in recent)
    else:
        votes = "  (none)"

    system = TEMPLATE.read_text().replace("FEEDBACK_VOTES_PLACEHOLDER", votes)
    user = "\n".join(format_story(i, s) for i, s in enumerate(stories, 1)) + "\n"

    Path(sys.argv[3]).write_text(system)
    Path(sys.argv[4]).write_text(user)

    print(f"Built prompt: {len(stories)} stories, {len(recent)}/{len(feedback)} votes "
          f"(last {FEEDBACK_DAYS}d), {len(system) + len(user)} chars", file=sys.stderr)


if __name__ == "__main__":
    main()
