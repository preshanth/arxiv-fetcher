"""
Regenerate docs/index.md - the site homepage listing every verified
paper, newest first, with its LLM-assigned tags. Run after pipeline.py
so the index reflects whatever is currently in SQLite.
"""

import sqlite3
from pathlib import Path


def build_index(conn: sqlite3.Connection, docs_dir: str = "docs") -> str:
    rows = conn.execute(
        "SELECT arxiv_id, title, published, llm_tags FROM papers "
        "WHERE verified = 1 ORDER BY published DESC, processed_at DESC"
    ).fetchall()

    lines = [
        "---",
        "title: Home",
        "layout: home",
        "---",
        "",
        "# Daily Astronomy Paper Digest",
        "",
        f"{len(rows)} verified papers.",
        "",
    ]

    for row in rows:
        tags = row["llm_tags"] or ""
        lines.append(f"- [{row['title']}](papers/{row['arxiv_id']}.md) — {row['published']}")
        if tags:
            lines.append(f"  <small>{tags}</small>")

    output_path = Path(docs_dir) / "index.md"
    output_path.write_text("\n".join(lines) + "\n")
    return str(output_path)


if __name__ == "__main__":
    from db import get_connection

    conn = get_connection("arxiv_papers.db")
    path = build_index(conn)
    conn.close()
    print(f"Wrote {path}")
