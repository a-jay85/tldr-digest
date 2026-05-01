#!/usr/bin/env python3
"""Gmail operations for the TLDR digest pipeline.

Subcommands:
    fetch   — Search for unread TLDR emails, save plaintext to emails/, write thread IDs to thread_ids.json
    draft   — Create a Gmail draft from digest_subject.txt and digest.html
    archive — Remove UNREAD and INBOX labels from threads listed in thread_ids.json

Requires credentials.json (OAuth client) in the project root.
On first run, opens a browser for consent and saves token.json.
"""

import base64
import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
PROJECT_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = PROJECT_DIR / "credentials.json"
TOKEN_FILE = PROJECT_DIR / "token.json"


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(
                    f"Missing {CREDENTIALS_FILE}.\n"
                    "Create an OAuth 2.0 Client ID (Desktop) at:\n"
                    "  https://console.cloud.google.com/apis/credentials\n"
                    "Download the JSON and save it as credentials.json in the project root.",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def extract_plaintext(payload: dict) -> str:
    """Recursively extract plaintext from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = extract_plaintext(part)
        if text:
            return text
    if mime == "text/html" and not payload.get("parts"):
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def cmd_fetch():
    service = get_service()
    emails_dir = PROJECT_DIR / "emails"
    emails_dir.mkdir(exist_ok=True)
    for f in emails_dir.glob("tldr_*.txt"):
        f.unlink()

    query = "from:dan@tldrnewsletter.com is:unread in:inbox"
    thread_ids = []
    page_token = None
    threads = []

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.users().threads().list(**kwargs).execute()
        threads.extend(resp.get("threads", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not threads:
        print("No unread TLDR emails found.", file=sys.stderr)
        json.dump([], open(PROJECT_DIR / "thread_ids.json", "w"))
        sys.exit(0)

    if len(threads) < 3:
        print(f"Warning: only {len(threads)} emails found (expected 3+).", file=sys.stderr)

    for i, t in enumerate(threads, 1):
        tid = t["id"]
        thread_ids.append(tid)
        thread = service.users().threads().get(userId="me", id=tid, format="full").execute()
        for msg in thread.get("messages", []):
            text = extract_plaintext(msg.get("payload", {}))
            if text:
                out_file = emails_dir / f"tldr_{i}.txt"
                out_file.write_text(text, encoding="utf-8")
                print(f"  Saved {out_file.name} ({len(text)} chars)", file=sys.stderr)
                break

    with open(PROJECT_DIR / "thread_ids.json", "w") as f:
        json.dump(thread_ids, f, indent=2)

    print(f"Fetched {len(threads)} emails, thread IDs written to thread_ids.json", file=sys.stderr)


def cmd_draft():
    service = get_service()
    subject_file = PROJECT_DIR / "digest_subject.txt"
    html_file = PROJECT_DIR / "digest.html"

    if not subject_file.exists() or not html_file.exists():
        print("Missing digest_subject.txt or digest.html", file=sys.stderr)
        sys.exit(1)

    subject = subject_file.read_text().strip()
    html_body = html_file.read_text()

    from email.mime.text import MIMEText

    msg = MIMEText(html_body, "html")
    msg["to"] = "REDACTED_EMAIL"
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()

    print(f"Draft created: id={draft['id']}", file=sys.stderr)


def cmd_archive():
    service = get_service()
    ids_file = PROJECT_DIR / "thread_ids.json"

    if not ids_file.exists():
        print("No thread_ids.json found — nothing to archive.", file=sys.stderr)
        return

    thread_ids = json.loads(ids_file.read_text())
    for tid in thread_ids:
        service.users().threads().modify(
            userId="me",
            id=tid,
            body={"removeLabelIds": ["UNREAD", "INBOX"]},
        ).execute()

    print(f"Archived {len(thread_ids)} threads (removed UNREAD + INBOX labels).", file=sys.stderr)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "draft", "archive"):
        print("Usage: gmail_ops.py {fetch|draft|archive}", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "fetch":
        cmd_fetch()
    elif cmd == "draft":
        cmd_draft()
    elif cmd == "archive":
        cmd_archive()


if __name__ == "__main__":
    main()
