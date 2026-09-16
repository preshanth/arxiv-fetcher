"""
Orchestrates the full nightly pipeline:
fetch -> tag-filter -> PDF parse -> generate -> verify -> (pass) embed,
store, render Markdown.

Replaces agents.py/crew.py - CrewAI added no value once this is two flat
generate/verify calls per paper rather than a multi-agent workflow.
"""

import sys
import yaml
from array import array
from datetime import datetime

from arxiv_fetcher import ArxivFetcher
from pdf_pipeline import process_paper as parse_pdf, pick_key_figure
from llm_client import TACCClient
from db import get_connection, upsert_paper
from render import render_paper


def pack_embedding(vector: list) -> bytes:
    return array("f", vector).tobytes()


def process_one_paper(paper: dict, tacc: TACCClient, cache_dir: str, max_revisions: int = 2) -> dict:
    """
    Run one paper through parse -> generate -> verify -> revise (up to
    max_revisions times) -> (pass) embed. A revision feeds the verifier's
    specific objections back to the generator rather than discarding the
    draft outright on the first failure.
    """
    row = dict(paper)  # arxiv_id, title, authors, abstract, published, tag_score, matched_tags, ...

    print(f"\n{'='*70}\n{paper['title'][:65]}\n{'='*70}")

    parsed = parse_pdf(paper["arxiv_id"], paper["pdf_url"], cache_dir=cache_dir)
    print(f"  Parsed: {len(parsed['full_text'])} chars, {len(parsed['figures'])} figures")

    gen_model, ver_model = tacc.rotator.next_pair()
    row["generator_model"] = gen_model
    row["verifier_model"] = ver_model

    llm_tags = tacc.classify_tags(paper, gen_model)
    row["llm_tags"] = llm_tags
    print(f"  Tags ({gen_model}): {llm_tags}")

    draft = tacc.generate(paper, parsed["full_text"], gen_model)
    print(f"  Generated ({gen_model}): {len(draft)} chars")

    verify_result = tacc.verify(draft, parsed["full_text"], ver_model)
    attempt = 0
    while not verify_result["passed"] and attempt < max_revisions:
        attempt += 1
        print(f"  Verify attempt {attempt} FAILED - {verify_result['notes'][:100]}")
        print(f"  Revising ({gen_model})...")
        draft = tacc.revise(draft, parsed["full_text"], verify_result["notes"], gen_model)
        verify_result = tacc.verify(draft, parsed["full_text"], ver_model)

    row["draft"] = draft
    row["verified"] = 1 if verify_result["passed"] else 0
    row["verify_notes"] = verify_result["notes"]
    status = "PASSED" if verify_result["passed"] else "FAILED"
    print(f"  Final ({ver_model}) after {attempt} revision(s): {status} - {verify_result['notes'][:100]}")

    key_figure = pick_key_figure(parsed["figures"], draft)
    row["figure_path"] = key_figure.get("path")

    if verify_result["passed"]:
        embedding = tacc.embed(draft)
        row["embedding"] = pack_embedding(embedding)
    else:
        row["embedding"] = None

    return row


def run(config_path: str = "config.yaml", days_back: int = 1, max_papers: int = None):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    cache_dir = config["output"]["cache_dir"]

    print("Step 1: Fetching and tag-filtering papers...")
    fetcher = ArxivFetcher(config_path)
    papers = fetcher.fetch_papers(days_back=days_back)

    if not papers:
        print("No papers matched. Exiting.")
        return

    # No artificial cap by default - process everything the tag filter
    # accepted. max_papers is an explicit opt-in (e.g. for a quick test run).
    if max_papers:
        papers = papers[:max_papers]
    print(f"\nStep 2: Processing {len(papers)} papers through generate/verify pipeline...")

    tacc = TACCClient(config_path)
    conn = get_connection(config["output"].get("db_path", "arxiv_papers.db"))

    passed_count = 0
    failed_count = 0

    for paper in papers:
        try:
            row = process_one_paper(paper, tacc, cache_dir)
        except Exception as e:
            print(f"  ERROR processing {paper['arxiv_id']}: {e}")
            failed_count += 1
            continue

        upsert_paper(conn, row)

        if row["verified"]:
            db_row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (row["arxiv_id"],)
            ).fetchone()
            markdown_path = render_paper(db_row, docs_dir=config["output"].get("docs_dir", "docs"))
            conn.execute(
                "UPDATE papers SET markdown_path = ? WHERE arxiv_id = ?",
                (markdown_path, row["arxiv_id"]),
            )
            conn.commit()
            passed_count += 1
        else:
            failed_count += 1

    conn.close()

    print(f"\n{'='*70}")
    print(f"Pipeline complete: {passed_count} passed, {failed_count} failed/errored")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("max_papers", nargs="?", type=int, default=None)
    parser.add_argument("--days", type=int, default=1, help="Fetch window in days")
    args = parser.parse_args()

    run(days_back=args.days, max_papers=args.max_papers)
