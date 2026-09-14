#!/usr/bin/env python3
"""Merge LLM scores back onto full story records.

Usage:
    python3 merge_scores.py claude_output.json stories_fresh.json scored_stories.json

claude_output.json is the `claude -p --output-format json` result. Its
structured_output is {"scores": [{"i": <1-based index>, "score": int, "why": str?}]}.

Applies the cutoff rules deterministically (drop < 20; if more than 25 remain,
also drop < 30), joins on index, sorts by score, and writes scored_stories.json.
Exits non-zero if the output is missing/malformed or too few stories were scored,
so the caller's retry loop can kick in.
"""

import json
import sys

MIN_SCORE = 20
CROWDED_MIN_SCORE = 30
CROWDED_AT = 25
MIN_COVERAGE = 0.8


def fail(msg: str):
    print(f"ERROR: scoring validation failed: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <claude_output.json> <stories_fresh.json> <scored_stories.json>",
              file=sys.stderr)
        sys.exit(1)

    raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"claude output is not JSON ({e}): {raw[:300]!r}")

    if out.get("is_error"):
        fail(f"claude reported an error: {out.get('result')!r}")

    scores = (out.get("structured_output") or {}).get("scores")
    if scores is None:
        # Fall back to parsing the text result in case structured_output is absent.
        try:
            scores = json.loads(out.get("result") or "").get("scores")
        except Exception:
            scores = None
    if not isinstance(scores, list):
        fail(f"no scores array in output: {str(out.get('result'))[:300]!r}")

    stories = json.load(open(sys.argv[2]))
    n = len(stories)

    by_index = {}
    for r in scores:
        i, score = r.get("i"), r.get("score")
        if not isinstance(i, int) or not (1 <= i <= n):
            print(f"  warning: skipping entry with bad index: {r}", file=sys.stderr)
            continue
        if not isinstance(score, int):
            fail(f"bad score type: {r}")
        by_index[i] = r

    if len(by_index) < n * MIN_COVERAGE:
        fail(f"only {len(by_index)}/{n} stories scored")
    if len(by_index) < n:
        missing = sorted(set(range(1, n + 1)) - set(by_index))
        print(f"  warning: {len(missing)} unscored stories dropped: {missing}", file=sys.stderr)

    merged = []
    for i, r in by_index.items():
        merged.append({**stories[i - 1],
                       "score": max(0, min(100, r["score"])),
                       "rationale": (r.get("why") or "").strip()})

    kept = [s for s in merged if s["score"] >= MIN_SCORE]
    if len(kept) > CROWDED_AT:
        kept = [s for s in kept if s["score"] >= CROWDED_MIN_SCORE]
    kept.sort(key=lambda s: s["score"], reverse=True)

    with open(sys.argv[3], "w") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)
        f.write("\n")

    u = out.get("usage") or {}
    print(f"Scoring validated: {len(kept)} kept of {len(merged)} scored "
          f"(tokens: in={u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)}, "
          f"out={u.get('output_tokens', 0)}; turns={out.get('num_turns')})")


if __name__ == "__main__":
    main()
