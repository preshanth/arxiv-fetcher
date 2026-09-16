# ArXiv Daily Paper Analyzer

An automated pipeline for daily astronomy paper summaries from arXiv: full-paper ingestion, dual-model generate-and-verify summarization against a TACC-hosted OpenAI-compatible inference endpoint, and publication to a searchable static site.

## Overview

This system fetches daily astronomy papers from arXiv, filters them based on configurable research interests, downloads and parses the full PDF (not just the abstract), and produces an Astrobites-style summary that is fact-checked against the paper's own text before publication. Verified summaries are stored in SQLite and rendered as Markdown for a GitHub Pages site with both lexical and semantic search.

## Features

- Automated paper retrieval from arXiv categories (astro-ph.IM, GA, CO, HE)
- Tag-based filtering using hierarchical keyword matching
- Full PDF parsing (PyMuPDF) for both summarization and figure extraction
- Generate-then-verify pipeline: one model drafts an Astrobites-style summary from the full paper text, a different model fact-checks every claim against that text before publication
- Model rotation across a pool of large models on TACC's endpoint, so the verifier is never the same model that wrote the draft
- Key-figure selection: the figure whose caption best matches the summary's key results is pulled into the rendered page
- SQLite as the source of truth, with FTS5 lexical search and exported embeddings for client-side semantic search
- Runs entirely against TACC's OpenAI-compatible endpoint — no local LLM required

## Architecture

```
ArxivFetcher → tag filter → PDF download/parse (PyMuPDF)
    → Generator (rotated TACC model) → Astrobites-style draft
    → Verifier (rotated TACC model, != generator) → fact-check against full text
    → (pass only) Embed summary (E5-Mistral-7B-Instruct) → SQLite + rendered Markdown
```

Papers that fail verification are still stored (with the verifier's rejection notes) for traceability, but are not rendered or published.

### Components

- **arxiv_fetcher.py**: Fetches papers from the arXiv API and applies tag filtering
- **tags.py**: Tag matching with keyword extraction and scoring
- **pdf_pipeline.py**: Downloads and parses PDFs (full text + figures + captions) via PyMuPDF
- **llm_client.py**: TACC endpoint wrapper — generate, verify, embed, with model rotation
- **db.py**: SQLite schema, FTS5 lexical search, subscriber storage
- **render.py**: Renders a verified DB row to Markdown for the GitHub Pages site
- **export_vectors.py**: Exports verified embeddings for client-side semantic search
- **pipeline.py**: Orchestrates the full nightly run
- **config.yaml**: Configuration for tags, categories, and TACC settings
- **test_tacc.py**: Tests TACC endpoint connectivity and configured models

## Installation

### Prerequisites

- [pixi](https://pixi.sh/) for environment management
- A TACC (or other OpenAI-compatible) inference endpoint and API key

### Setup

1. Install dependencies:
   ```bash
   pixi install
   ```

2. Set your TACC API key in a `.env` file (gitignored, never commit this):
   ```
   TACC_API_KEY=your-key-here
   ```

3. Test the TACC connection:
   ```bash
   pixi run python test_tacc.py
   ```

4. Edit `config.yaml` to configure research tags and the model rotation pool (optional)

## Usage

### Run the Full Pipeline

```bash
pixi run python pipeline.py        # process up to config.filtering.max_papers_per_day
pixi run python pipeline.py 2      # cap to 2 papers, useful for testing
```

Outputs:
- `arxiv_papers.db` — SQLite database (source of truth)
- `docs/papers/<arxiv_id>.md` — rendered Markdown per verified paper
- `docs/assets/figures/` — extracted key figures

### Fetch Papers Only

```bash
pixi run python arxiv_fetcher.py
```

Output: `arxiv_papers/papers_YYYYMMDD.json`

### Export Search Vectors

```bash
pixi run python export_vectors.py
```

Output: `docs/search/vectors.bin`, `docs/search/ids.json`

### Test Components

```bash
pixi run python tags.py          # test tag matching
pixi run python test_tacc.py     # test TACC connectivity and configured models
pixi run python pdf_pipeline.py  # smoke test PDF parsing
pixi run python llm_client.py    # smoke test generate/verify/embed
pixi run python db.py            # smoke test SQLite storage + FTS5 search
pixi run python render.py        # smoke test Markdown rendering
```

## Configuration

### Research Tags (config.yaml)

Define research interests using hierarchical tags:

```yaml
active_tags:
  facilities:
    - vla
    - meerkat
    - alma

  techniques:
    - radio_interferometry
    - polarimetry

  data_processing:
    - calibration
    - rfi_mitigation

  computational:
    - machine_learning
    - gpu_acceleration

  science_topics:
    - cosmic_magnetism
    - absorption_lines
```

### ArXiv Categories

```yaml
arxiv_categories:
  - "astro-ph.IM"  # Instrumentation and Methods
  - "astro-ph.GA"  # Astrophysics of Galaxies
  - "astro-ph.CO"  # Cosmology
  - "astro-ph.HE"  # High Energy
```

### TACC Configuration

```yaml
tacc:
  base_url: "https://ai.tejas.tacc.utexas.edu"
  api_key_env: "TACC_API_KEY"   # key is read from this env var, never stored here
  models:
    - "DeepSeek-V3.2"
    - "Mistral-Large-3-675B-Instruct-2512"
    - "Qwen3-235B-A22B-Instruct-2507"
    - "gpt-oss-120b"
  embedding_model: "E5-Mistral-7B-Instruct"
```

The pipeline rotates through `models` for the generator/verifier roles per paper, guaranteeing the verifier is never the same model that wrote the draft.

### Keyword Patterns

Extend keyword patterns for tag matching:

```yaml
keyword_patterns:
  your_tag:
    - "keyword one"
    - "keyword phrase"
```

## How It Works

### Tag Filtering

1. Fetches papers from specified arXiv categories
2. Extracts keywords from title and abstract
3. Matches against configured tag patterns
4. Scores papers based on number of tag matches
5. Keeps papers with score ≥ 1

### Generate-and-Verify

1. **Parse**: full PDF text and figures (with captions) are extracted via PyMuPDF
2. **Generate**: one rotated model writes an Astrobites-style summary (Why This Matters / What They Did / Key Results / What's Next) grounded in the full text
3. **Verify**: a different rotated model checks every claim in the draft against the paper's full text, returning a pass/fail and specific notes on any discrepancy
4. **Publish**: only papers that pass verification are embedded, stored, and rendered to the site; failed papers remain in SQLite with the verifier's notes for traceability

## System Requirements

- pixi
- Internet connection for the arXiv API and TACC endpoint

## Status / Not Yet Implemented

- GitHub Pages site build (Pagefind lexical index, semantic search frontend, Cloudflare Worker for query-time embedding)
- Email digest distribution (subscriber table exists in SQLite; sending is not yet built)
- Slack integration
- Nightly cron/systemd timer (not installed automatically)

## References

- [arXiv API](https://arxiv.org/help/api/)
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- [Pagefind](https://pagefind.app/)

---

**Note**: This is a research tool. Generated summaries are fact-checked against the source paper before publication, but should still be verified by consulting the original paper for anything load-bearing.
