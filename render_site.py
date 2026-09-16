"""
Regenerate the full docs/ site (papers/, index.md) from arxiv_papers.db.
Run before `jekyll build` in CI — docs/papers/, docs/index.md, and
docs/assets/figures/ are gitignored, so nothing rendered is committed;
this script is what recreates them from the DB on each build.
"""

from db import get_connection
from render import render_paper
from site_index import build_index


def render_site(db_path: str = "arxiv_papers.db", docs_dir: str = "docs") -> int:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM papers WHERE verified = 1").fetchall()
    for row in rows:
        render_paper(row, docs_dir=docs_dir)
    build_index(conn, docs_dir=docs_dir)
    conn.close()
    return len(rows)


if __name__ == "__main__":
    count = render_site()
    print(f"Rendered {count} papers + index")
