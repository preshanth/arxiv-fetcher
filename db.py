"""
SQLite storage: source of truth for papers, verification status, and
subscribers. FTS5 provides lexical search; semantic search vectors are
exported separately (export_vectors.py) for the static site.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    published TEXT,
    tag_score INTEGER,
    matched_tags TEXT,
    draft TEXT,
    verified INTEGER,
    verify_notes TEXT,
    generator_model TEXT,
    verifier_model TEXT,
    figure_path TEXT,
    markdown_path TEXT,
    embedding BLOB,
    processed_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title, abstract, draft,
    content='papers',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, abstract, draft)
    VALUES (new.rowid, new.title, new.abstract, new.draft);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, draft)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.draft);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, draft)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.draft);
    INSERT INTO papers_fts(rowid, title, abstract, draft)
    VALUES (new.rowid, new.title, new.abstract, new.draft);
END;

CREATE TABLE IF NOT EXISTS subscribers (
    email TEXT PRIMARY KEY,
    subscribed_at TEXT,
    active INTEGER DEFAULT 1
);
"""


def get_connection(db_path: str = "arxiv_papers.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_paper(conn: sqlite3.Connection, paper: Dict) -> None:
    """
    Insert or replace a paper row. `paper` should have keys matching the
    `papers` columns; missing keys default to None. The FTS triggers keep
    papers_fts in sync automatically on INSERT/UPDATE/DELETE.
    """
    columns = [
        "arxiv_id", "title", "authors", "abstract", "published",
        "tag_score", "matched_tags", "draft", "verified", "verify_notes",
        "generator_model", "verifier_model", "figure_path", "markdown_path",
        "embedding", "processed_at",
    ]
    row = {col: paper.get(col) for col in columns}
    if row["processed_at"] is None:
        row["processed_at"] = datetime.now().isoformat()
    if isinstance(row.get("authors"), list):
        row["authors"] = ", ".join(row["authors"])
    if isinstance(row.get("matched_tags"), list):
        row["matched_tags"] = ", ".join(row["matched_tags"])

    placeholders = ", ".join(f":{col}" for col in columns)
    col_list = ", ".join(columns)
    conn.execute(
        f"INSERT OR REPLACE INTO papers ({col_list}) VALUES ({placeholders})",
        row,
    )
    conn.commit()


def search_fts(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT papers.* FROM papers_fts
        JOIN papers ON papers.rowid = papers_fts.rowid
        WHERE papers_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )
    return cursor.fetchall()


def get_verified_papers(conn: sqlite3.Connection, since: Optional[str] = None) -> List[sqlite3.Row]:
    if since:
        cursor = conn.execute(
            "SELECT * FROM papers WHERE verified = 1 AND processed_at >= ? ORDER BY processed_at DESC",
            (since,),
        )
    else:
        cursor = conn.execute("SELECT * FROM papers WHERE verified = 1 ORDER BY processed_at DESC")
    return cursor.fetchall()


def add_subscriber(conn: sqlite3.Connection, email: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO subscribers (email, subscribed_at, active) VALUES (?, ?, 1)",
        (email, datetime.now().isoformat()),
    )
    conn.commit()


def get_active_subscribers(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.execute("SELECT email FROM subscribers WHERE active = 1")
    return [row["email"] for row in cursor.fetchall()]


if __name__ == "__main__":
    # Smoke test: store the paper generated/verified earlier in the session.
    test_db = "test_arxiv.db"
    Path(test_db).unlink(missing_ok=True)
    conn = get_connection(test_db)

    upsert_paper(conn, {
        "arxiv_id": "2609.17382v1",
        "title": "Assessing ionospheric effects on image quality in the LOFAR Decametre Sky Survey",
        "authors": ["Test Author"],
        "abstract": "Test abstract about ionospheric decorrelation and LOFAR calibration.",
        "published": "2026-09-14",
        "tag_score": 2,
        "matched_tags": ["facility_lofar", "calibration"],
        "draft": "## Why This Matters\nIonospheric decorrelation affects LOFAR imaging...",
        "verified": 1,
        "verify_notes": "Minor rounding discrepancies, otherwise accurate",
        "generator_model": "DeepSeek-V3.2",
        "verifier_model": "Mistral-Large-3-675B-Instruct-2512",
        "figure_path": "arxiv_cache/figures/2609.17382v1_p7_0.png",
        "markdown_path": "docs/papers/2609.17382v1.md",
    })

    results = search_fts(conn, "ionospheric LOFAR")
    print(f"FTS search 'ionospheric LOFAR': {len(results)} result(s)")
    for r in results:
        print(f"  {r['arxiv_id']}: {r['title'][:60]}")

    verified = get_verified_papers(conn)
    print(f"Verified papers: {len(verified)}")

    conn.close()
    Path(test_db).unlink()
    print("Smoke test passed, test db cleaned up")
