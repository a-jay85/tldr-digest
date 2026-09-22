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
import time
import urllib.request
from email.header import decode_header, make_header
from pathlib import Path

from config_util import load_config

PROJECT_DIR = Path(__file__).resolve().parent


def verify_sent(subject: str, since_ts: float) -> bool:
    """Check the owner's mailbox for a digest sent after `since_ts` with this subject.

    Apps Script /exec POSTs 302-redirect to script.googleusercontent.com; a
    404/timeout on that redirect target happens *after* the script already ran
    and sent the mail (observed 2026-09-14). So a transport-level failure is
    ambiguous, not a failure — ask Gmail directly instead of guessing.

    Out-of-band on purpose: re-POSTing would re-use the same flaky channel and
    could send a second copy. gmail_ops' gmail.modify scope includes read, and
    the digest is sent from the owner to the owner, so it is visible here.

    `since_ts` (epoch seconds, captured just before the POST) is what makes the
    match trustworthy: subjects are date-based, so every digest sent on a given
    day shares one. Without it, a second run's 404 would match the *first* run's
    email and exit 0, marking the second run's new stories seen but never sent.
    """
    try:
        from gmail_ops import get_service
        service = get_service()
    except Exception as e:  # noqa: BLE001 - verification is best-effort
        # Inconclusive, not negative — Gmail itself was unreachable. We still
        # return False (aborting is the safe default), but log it distinctly so
        # a postmortem can tell "digest wasn't sent" from "couldn't tell".
        print(f"  VERIFY INCONCLUSIVE — could not check Gmail: {e}", file=sys.stderr)
        return False

    # Gmail's `subject:` operator is unreliable against the emoji in our
    # subjects, so match exactly in Python. The query window is deliberately
    # loose; internalDate vs since_ts does the real narrowing.
    cutoff = since_ts - 10  # slack for clock skew between here and Gmail
    for attempt in range(3):
        if attempt:
            time.sleep(5)
        try:
            resp = service.users().messages().list(
                userId="me", q="in:anywhere from:me newer_than:1d", maxResults=50,
            ).execute()
            for msg in resp.get("messages", []):
                meta = service.users().messages().get(
                    userId="me", id=msg["id"],
                    format="metadata", metadataHeaders=["Subject"],
                ).execute()
                try:
                    if int(meta["internalDate"]) / 1000 < cutoff:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue  # can't date it, can't trust it
                for h in meta.get("payload", {}).get("headers", []):
                    if h.get("name", "").lower() != "subject":
                        continue
                    raw = h.get("value", "")
                    try:
                        decoded = str(make_header(decode_header(raw)))
                    except Exception:  # noqa: BLE001
                        decoded = raw
                    if decoded.strip() == subject or raw.strip() == subject:
                        return True
        except Exception as e:  # noqa: BLE001
            print(f"  Gmail verification attempt {attempt + 1} failed: {e}",
                  file=sys.stderr)
    return False


def ambiguous_send(reason: str, subject: str, since_ts: float):
    """Handle a transport-level failure, where the digest may already be sent.

    Exits 0 if Gmail confirms delivery so digest-run can still archive threads
    and record seen URLs — skipping those would make tomorrow's run re-send the
    same stories. Exits 1 if unconfirmed, same as any other send failure.
    """
    print(f"Send may have failed: {reason}", file=sys.stderr)
    print("  checking Gmail to see whether the digest actually went out...",
          file=sys.stderr)
    if verify_sent(subject, since_ts):
        print(f"WARNING: {reason}, but the digest IS in your mailbox — "
              "treating as sent and continuing (no retry, to avoid a duplicate).",
              file=sys.stderr)
        sys.exit(0)
    print("  no matching digest found in Gmail — treating as a real failure.",
          file=sys.stderr)
    sys.exit(1)


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

    # Captured before the POST so verify_sent can tell *this* run's digest from
    # an earlier one with the same date-based subject.
    sent_at = time.time()

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 405:
            # The script answered, and answered "no doPost here" — nothing ran.
            print("Send failed: HTTP 405 — the deployment has no doPost. Push the "
                  "updated feedback_webapp.gs and redeploy (bin/deploy-appsscript).",
                  file=sys.stderr)
            sys.exit(1)
        # e.url is the URL that actually 404'd — usually the googleusercontent
        # redirect target, i.e. after the script ran. Log it for next time.
        ambiguous_send(f"HTTP {e.code} {e.reason} from {e.url}",
                       payload["subject"], sent_at)
    except urllib.error.URLError as e:
        ambiguous_send(f"could not reach web app: {e.reason}",
                       payload["subject"], sent_at)
    except TimeoutError:
        # Read timeout: the send may well have completed server-side.
        ambiguous_send("timed out waiting for the web app response",
                       payload["subject"], sent_at)

    # A not-yet-redeployed or wrong URL returns HTTP 200 with an HTML login/error
    # page rather than our JSON. But Google also serves an HTML error page from
    # the script.googleusercontent.com redirect target *after* doPost has already
    # run and sent the mail (seen 2026-09-22), so this is ambiguous like the
    # 404/timeout cases — check Gmail before calling it a failure.
    if "text/html" in content_type or raw.lstrip().startswith("<!"):
        print(f"  HTML response body (first 300 chars): {raw.lstrip()[:300]}",
              file=sys.stderr)
        ambiguous_send("web app returned HTML instead of JSON (doPost not deployed, "
                       "access not 'Anyone', or a post-send redirect error)",
                       payload["subject"], sent_at)

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
