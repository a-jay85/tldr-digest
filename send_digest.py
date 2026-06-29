#!/usr/bin/env python3
"""Send the built digest via the Apps Script web app's doPost endpoint.

Usage:
    python3 send_digest.py config.json

Reads digest_subject.txt + digest.html (produced by build_email.py) and POSTs
them to the web app's `sendDigest` action, which sends the email via GmailApp.
Replaces the Gmail-draft step: the script's OAuth (gmail.modify) can't send, so
delivery is delegated to Apps Script, which runs as the account owner.

POSTs to `apps_script_url` (the script's /exec deployment). Note `webapp_url` is
the static GitHub Pages redirect used for feedback GET links — it can't accept a
POST. That /exec deployment must be redeployed with the doPost code (see
bin/deploy-appsscript), or the POST hits old code and fails. Exits non-zero
unless the response body is {"status": "ok"}, so a stale/wrong deployment aborts
the run loudly rather than reporting a phantom send.
"""

import json
import sys
import urllib.request
from pathlib import Path

from config_util import load_config

PROJECT_DIR = Path(__file__).resolve().parent


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config.json>", file=sys.stderr)
        sys.exit(1)

    config = load_config(sys.argv[1])
    endpoint = config.get("apps_script_url", "")
    if not endpoint:
        print("No apps_script_url in config — set it in config.local.json.", file=sys.stderr)
        sys.exit(1)
    token = config.get("apps_script_token", "")

    subject_file = PROJECT_DIR / "digest_subject.txt"
    html_file = PROJECT_DIR / "digest.html"
    if not subject_file.exists() or not html_file.exists():
        print("Missing digest_subject.txt or digest.html — run build_email.py first.",
              file=sys.stderr)
        sys.exit(1)

    payload = {
        "action": "sendDigest",
        "token": token,
        "subject": subject_file.read_text(encoding="utf-8").strip(),
        "htmlBody": html_file.read_text(encoding="utf-8"),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "send_digest/1.0"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 405:
            print("Send failed: HTTP 405 — the deployment has no doPost. Push the "
                  "updated feedback_webapp.gs and redeploy (bin/deploy-appsscript).",
                  file=sys.stderr)
        else:
            print(f"Send failed: HTTP {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Send failed: could not reach web app: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # A not-yet-redeployed or wrong URL returns HTTP 200 with an HTML login/error
    # page rather than our JSON — treat that as failure, same as sync_feedback.py.
    if "text/html" in content_type or raw.lstrip().startswith("<!"):
        print("Send failed: web app returned HTML (doPost not deployed, or access "
              "not 'Anyone'). Redeploy with bin/deploy-appsscript.",
              file=sys.stderr)
        sys.exit(1)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"Send failed: non-JSON response: {raw[:200]}", file=sys.stderr)
        sys.exit(1)

    if result.get("status") != "ok":
        print(f"Send failed: {result.get('message', raw[:200])}", file=sys.stderr)
        sys.exit(1)

    print(result.get("message", "Digest sent."))


if __name__ == "__main__":
    main()
