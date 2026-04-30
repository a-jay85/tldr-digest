#!/usr/bin/env python3
"""Parse TLDR newsletter plaintext into structured JSON.

Usage:
    python3 parse_tldr.py <input_dir> <output_file>

Reads all .txt files in <input_dir> (one per newsletter), writes a JSON
array of story objects to <output_file>.
"""

import json
import re
import sys
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def clean_url(url: str) -> str:
    """Strip UTM params, trailing slash, www., and lowercase."""
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items()
              if not k.startswith("utm_")}
    cleaned_query = urlencode(params, doseq=True)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    cleaned = urlunparse((
        parsed.scheme,
        host,
        parsed.path.rstrip("/"),
        parsed.params,
        cleaned_query,
        ""
    ))
    return cleaned.lower()


def to_title_case(s: str) -> str:
    """Convert ALL CAPS to Title Case, preserving short words."""
    small_words = {"a", "an", "the", "and", "but", "or", "for", "nor",
                   "on", "at", "to", "by", "in", "of", "up", "as", "is",
                   "it", "vs", "via"}
    words = s.strip().split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i == 0 or lower not in small_words:
            result.append(word.capitalize())
        else:
            result.append(lower)
    return " ".join(result)


def detect_source(text: str) -> str:
    """Detect which TLDR newsletter from the header line."""
    for line in text.split("\n")[:30]:
        line_stripped = line.strip()
        if re.match(r"TLDR AI\s+\d{4}-\d{2}-\d{2}", line_stripped):
            return "TLDR AI"
        if re.match(r"TLDR (WEB )?DEV\s+\d{4}-\d{2}-\d{2}", line_stripped, re.IGNORECASE):
            return "TLDR Dev"
        if re.match(r"TLDR PRODUCT\s", line_stripped, re.IGNORECASE):
            return "TLDR Product"
        if re.match(r"TLDR\s+\d{4}-\d{2}-\d{2}", line_stripped):
            return "TLDR"
    return "TLDR"


def parse_links_section(text: str) -> dict[str, str]:
    """Extract [N] -> URL mapping from the Links: section."""
    links = {}
    in_links = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("links:"):
            in_links = True
            continue
        if in_links:
            m = re.match(r"\[(\d+)\]\s+(https?://\S+)", stripped)
            if m:
                links[m.group(1)] = m.group(2)
    return links


def parse_stories(text: str, source: str, links: dict[str, str]) -> list[dict]:
    """Extract stories from newsletter body."""
    stories = []
    lines = text.split("\n")

    skip_patterns = [
        r"\(SPONSOR\)",
        r"Love TLDR",
        r"Want to advertise",
        r"TLDR is a daily",
        r"refer a friend",
        r"If you have any comments",
    ]

    section_headers = {
        "HEADLINES & LAUNCHES", "DEEP DIVES & ANALYSIS", "QUICK LINKS",
        "OPINIONS & TUTORIALS", "LAUNCHES & TOOLS", "ARTICLES & TUTORIALS",
        "TOOLS & RESOURCES", "MISCELLANEOUS", "BIG TECH & STARTUPS",
        "SCIENCE & FUTURISTIC TECHNOLOGY", "PROGRAMMING, DESIGN & DATA SCIENCE",
        "RESEARCH & INNOVATION", "ENGINEERING & RESOURCES",
        "PRODUCT STRATEGY", "GROWTH & METRICS", "CAREER & SKILLS",
        "NEWS & TRENDS", "STRATEGIES & TACTICS", "RESOURCES & TOOLS",
    }

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            i += 1
            continue

        upper_line = line.upper()
        if any(header in upper_line for header in section_headers):
            i += 1
            continue

        m = re.match(
            r"^(.+?)\s*\((\d+)\s+MINUTE READ\)\s*\[(\d+)\]\s*$",
            line, re.IGNORECASE
        )
        if not m:
            m = re.match(
                r"^(.+?)\s*\(GITHUB REPO\)\s*\[(\d+)\]\s*$",
                line, re.IGNORECASE
            )
            if m:
                title_raw = m.group(1).strip()
                read_time = 0
                ref_num = m.group(2)
            else:
                i += 1
                continue
        else:
            title_raw = m.group(1).strip()
            read_time = int(m.group(2))
            ref_num = m.group(3)

        if "(SPONSOR)" in title_raw.upper():
            i += 1
            continue

        desc_lines = []
        i += 1
        while i < len(lines):
            dl = lines[i].strip()
            if not dl:
                if desc_lines:
                    break
                i += 1
                continue
            if re.match(r"^.+\(\d+\s+MINUTE READ\)\s*\[\d+\]", dl, re.IGNORECASE):
                break
            if re.match(r"^.+\(GITHUB REPO\)\s*\[\d+\]", dl, re.IGNORECASE):
                break
            desc_lines.append(dl)
            i += 1

        description = " ".join(desc_lines).strip()
        description = re.sub(r"\s*\[\d+\]", "", description)

        if any(re.search(p, description, re.IGNORECASE) for p in skip_patterns):
            continue

        original_url = links.get(ref_num, "")
        if not original_url:
            continue

        stories.append({
            "title": to_title_case(title_raw),
            "description": description,
            "url_original": original_url,
            "url_clean": clean_url(original_url),
            "read_time": read_time,
            "source": source,
        })

    return stories


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_dir> <output_file>", file=sys.stderr)
        sys.exit(1)

    input_dir = sys.argv[1]
    output_file = sys.argv[2]

    all_stories = []
    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith(".txt"):
            continue
        filepath = os.path.join(input_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        source = detect_source(text)
        links = parse_links_section(text)
        stories = parse_stories(text, source, links)
        all_stories.extend(stories)
        print(f"  {source}: {len(stories)} stories from {fname}", file=sys.stderr)

    seen_urls = set()
    deduped = []
    for s in all_stories:
        if s["url_clean"] not in seen_urls:
            seen_urls.add(s["url_clean"])
            deduped.append(s)

    print(f"  Total: {len(all_stories)} → {len(deduped)} after dedup", file=sys.stderr)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)

    print(f"Wrote {len(deduped)} stories to {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
