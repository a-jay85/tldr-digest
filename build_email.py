#!/usr/bin/env python3
"""Build the digest HTML email from scored stories JSON.

Usage:
    python3 build_email.py scored_stories.json config.json

Reads scored stories, generates HTML, writes digest.html and digest_subject.txt.
"""

import json
import sys
from datetime import datetime
from urllib.parse import quote


SCORE_COLORS = {"score-high": "#16a34a", "score-med": "#d97706", "score-low": "#a1a1aa"}


def score_class(score: int) -> str:
    if score >= 70:
        return "score-high"
    if score >= 40:
        return "score-med"
    return "score-low"


def build_story_html(story: dict, webapp_url: str) -> str:
    pill = score_class(story["score"])
    read_time = f'{story["read_time"]} min read' if story["read_time"] > 0 else "GitHub repo"

    feedback = ""
    if webapp_url:
        params_up = (
            f'?action=feedback&vote=up'
            f'&title={quote(story["title"], safe="")}'
            f'&url={quote(story["url_clean"], safe="")}'
            f'&source={quote(story["source"], safe="")}'
            f'&score={story["score"]}'
        )
        params_down = params_up.replace("vote=up", "vote=down")
        btn = (
            "display:inline-block;padding:4px 10px;border-radius:14px;"
            "font-size:13px;text-decoration:none;margin-right:6px;"
        )
        feedback = (
            f'    <div style="margin-top:8px;">'
            f'<a href="{webapp_url}{params_up}" '
            f'style="{btn}background:#f0fdf4;color:#16a34a;">'
            f'\U0001f44d More like this</a>'
            f'<a href="{webapp_url}{params_down}" '
            f'style="{btn}background:#fef2f2;color:#dc2626;">'
            f'\U0001f44e Less like this</a>'
            f'</div>'
        )

    return f"""  <div style="padding:16px 24px;border-bottom:1px solid #f0f0f0;">
    <div>
      <a href="{story['url_original']}" style="color:#18181b;font-size:15px;font-weight:600;text-decoration:none;line-height:1.35;">{story['title']}</a>
      <span style="display:inline-block;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;margin-left:6px;color:#fff;background:{SCORE_COLORS[pill]};">{story['score']}</span>
    </div>
    <div style="font-size:13px;color:#52525b;line-height:1.5;margin:6px 0 8px;">{story['description']}</div>
    <div style="font-size:11px;color:#a1a1aa;">
      <span style="background:#f4f4f5;padding:2px 6px;border-radius:3px;margin-right:6px;">{story['source']}</span>
      {read_time} · {story.get('rationale', '')}
    </div>
{feedback}
  </div>"""


MAX_FOR_YOU = 12
MAX_ALSO_TODAY = 12


def build_compact_html(story: dict) -> str:
    read_time = f'{story["read_time"]} min' if story["read_time"] > 0 else "repo"
    return (
        f'  <div style="padding:6px 24px;border-bottom:1px solid #f0f0f0;">'
        f'<a href="{story["url_original"]}" style="color:#18181b;font-size:14px;'
        f'text-decoration:none;">{story["title"]}</a>'
        f' <span style="font-size:11px;color:#a1a1aa;">— {story["source"]} · {read_time}</span>'
        f'</div>'
    )


def build_email(stories: list[dict], webapp_url: str) -> tuple[str, str]:
    today = datetime.now().strftime("%A, %B %-d, %Y")
    subject = f"\U0001f4cb TLDR Digest — {today}"

    for_you = [s for s in stories if s["score"] >= 60]
    also_today = [s for s in stories if 20 <= s["score"] < 60]
    for_you.sort(key=lambda s: s["score"], reverse=True)
    also_today.sort(key=lambda s: s["score"], reverse=True)
    for_you = for_you[:MAX_FOR_YOU]
    also_today = also_today[:MAX_ALSO_TODAY]

    all_included = for_you + also_today
    sources = sorted(set(s["source"] for s in all_included))
    count = len(all_included)

    for_you_html = "\n".join(build_story_html(s, webapp_url) for s in for_you)
    also_html = "\n".join(build_compact_html(s) for s in also_today)

    footer_feedback = ""
    if webapp_url:
        footer_feedback = (
            f'<br><a href="{webapp_url}?action=stats" '
            f'style="color:#71717a;">View feedback stats</a>'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:620px;margin:0 auto;background:#ffffff;">
  <div style="background:#18181b;color:#ffffff;padding:28px 24px 20px;">
    <h1 style="margin:0 0 4px;font-size:22px;font-weight:700;letter-spacing:-0.3px;">\U0001f4cb Your TLDR Digest</h1>
    <p style="font-size:13px;color:#a1a1aa;margin:0;">{today} · {count} stories from {', '.join(sources)}</p>
  </div>

  <div><span style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#ffffff;padding:6px 12px;margin:24px 24px 12px;display:inline-block;border-radius:3px;background:#2563eb;">⭐ For You</span></div>
{for_you_html}

  <div><span style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#ffffff;padding:6px 12px;margin:24px 24px 12px;display:inline-block;border-radius:3px;background:#71717a;">📰 Also Today</span></div>
{also_html}

  <div style="padding:20px 24px;background:#fafafa;border-top:1px solid #e4e4e7;font-size:12px;color:#a1a1aa;text-align:center;">
    Your TLDR Digest · Tap 👍/👎 to improve future digests{footer_feedback}
  </div>
</div>
</body>
</html>"""

    return subject, html


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <scored_stories.json> <config.json>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        stories = json.load(f)

    with open(sys.argv[2]) as f:
        config = json.load(f)

    webapp_url = config.get("webapp_url", "")

    subject, html = build_email(stories, webapp_url)

    with open("digest_subject.txt", "w") as f:
        f.write(subject)
    with open("digest.html", "w") as f:
        f.write(html)

    for_you_n = len([s for s in stories if s["score"] >= 60][:MAX_FOR_YOU])
    also_n = len([s for s in stories if 20 <= s["score"] < 60][:MAX_ALSO_TODAY])
    print(f"Built digest: {for_you_n + also_n} stories ({for_you_n} For You, {also_n} Also Today)", file=sys.stderr)
    print(f"  Subject: {subject}", file=sys.stderr)
    print(f"  Written to: digest.html, digest_subject.txt", file=sys.stderr)


if __name__ == "__main__":
    main()
