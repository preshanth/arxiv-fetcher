"""
Export verified papers' embeddings to a compact static binary for the
GitHub Pages site's client-side semantic search. int8-quantized to keep
size down; a single global scale factor is stored in ids.json for
client-side dequantization.
"""

import json
import sqlite3
from array import array
from pathlib import Path


def quantize(vectors: list, scale: float = 127.0) -> bytes:
    """Quantize float32 vectors (assumed roughly in [-1, 1]) to int8."""
    out = bytearray()
    for vec in vectors:
        for v in vec:
            clamped = max(-1.0, min(1.0, v))
            out.append(int(round(clamped * scale)) & 0xFF)
    return bytes(out)


def export(db_path: str = "arxiv_papers.db", output_dir: str = "docs/search"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT arxiv_id, title, markdown_path, embedding FROM papers "
        "WHERE verified = 1 AND embedding IS NOT NULL"
    ).fetchall()
    conn.close()

    if not rows:
        print("No verified papers with embeddings to export.")
        return

    vectors = [array("f", row["embedding"]).tolist() for row in rows]
    dims = len(vectors[0])

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    (output_path / "vectors.bin").write_bytes(quantize(vectors))

    ids = {
        "dims": dims,
        "scale": 127.0,
        "papers": [
            {"arxiv_id": r["arxiv_id"], "title": r["title"], "markdown_path": r["markdown_path"]}
            for r in rows
        ],
    }
    (output_path / "ids.json").write_text(json.dumps(ids, indent=2))

    print(f"Exported {len(rows)} vectors ({dims} dims each) to {output_path}/")


if __name__ == "__main__":
    export()
