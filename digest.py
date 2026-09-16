"""
Nightly email digest: newly-verified papers since the last run, sent to
active subscribers. STUBBED - no transactional email provider is
configured yet, so this prints what would be sent instead of sending.

To finish: pick a provider (SendGrid/Mailgun/SES recommended over raw
SMTP for deliverability), add its credentials via env var (same pattern
as TACC_API_KEY - .env, never config.yaml), and replace send_digest's
body with the provider's API call.
"""

import yaml
from datetime import datetime, timedelta

from db import get_connection, get_verified_papers, get_active_subscribers


def build_digest_text(papers) -> str:
    if not papers:
        return "No new verified papers today."

    lines = [f"{len(papers)} new astronomy paper(s) today:\n"]
    for p in papers:
        lines.append(f"- {p['title']}")
        lines.append(f"  https://arxiv.org/abs/{p['arxiv_id'].split('v')[0]}")
        lines.append(f"  Tags: {p['llm_tags'] or 'none'}")
        lines.append("")
    return "\n".join(lines)


def send_digest(config_path: str = "config.yaml", since_hours: int = 24):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    conn = get_connection(config["output"].get("db_path", "arxiv_papers.db"))

    since = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    papers = get_verified_papers(conn, since=since)
    subscribers = get_active_subscribers(conn)

    digest_text = build_digest_text(papers)

    if not subscribers:
        print("No active subscribers. Digest would have been:\n")
        print(digest_text)
        conn.close()
        return

    print(f"[STUB - not actually sending] Would email {len(subscribers)} subscriber(s):")
    for email in subscribers:
        print(f"  -> {email}")
    print("\n--- Digest content ---\n")
    print(digest_text)

    conn.close()


if __name__ == "__main__":
    send_digest()
