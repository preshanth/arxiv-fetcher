# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pixi install                # resolve/create env from pixi.toml (conda-forge)
pixi run python test_tacc.py    # verify TACC endpoint + configured models/embedding model are live
pixi run python tags.py         # run TagMatcher's built-in test cases (3 sample papers)
pixi run python arxiv_fetcher.py    # fetch + tag-filter only -> arxiv_papers/papers_YYYYMMDD.json
pixi run python pdf_pipeline.py     # smoke test: download+parse one hardcoded arxiv_id
pixi run python llm_client.py       # smoke test: generate+verify+embed one paper against TACC
pixi run python db.py               # smoke test: SQLite insert + FTS5 search
pixi run python render.py           # smoke test: render one DB row to Markdown
pixi run python pipeline.py [N]     # full nightly pipeline, capped to N papers (default: config filtering.max_papers_per_day)
pixi run python export_vectors.py   # export verified papers' embeddings to docs/search/ for site semantic search
```

There is no test suite beyond `__main__` smoke-test blocks in most modules (no pytest/unittest). No lint config present. The TACC API key is read from the `TACC_API_KEY` env var via `.env` (gitignored, loaded with `python-dotenv`) — never stored in `config.yaml`.

## Architecture

Full pipeline (`pipeline.py`): `ArxivFetcher.fetch_papers` → tag-filter (`TagMatcher`, unchanged) → `pdf_pipeline.process_paper` (download + parse) → `llm_client.TACCClient.generate` → `pdf_pipeline.pick_key_figure` → `llm_client.TACCClient.verify` → on pass: `llm_client.TACCClient.embed` → `db.upsert_paper` → `render.render_paper`. Each paper is wrapped in its own try/except in `pipeline.py`'s `run()` loop so one failure doesn't abort the batch — failed/errored papers are still counted and (if they got that far) stored in SQLite with `verified=0` and the verifier's rejection reason, for traceability.

**Tag filtering** (`arxiv_fetcher.py` + `tags.py`, unchanged from original design): `TagMatcher.score_paper` combines `extract_keywords` (regex word-boundary match against `keyword_patterns` in config.yaml) and `_check_facilities` (substring match against `active_tags.facilities`, tags prefixed `facility_`). Score is `len(matched_tags)`; `ArxivFetcher.fetch_papers` keeps anything with `score >= 1` — the `decision` field (`accept`/`llm_validate`/`reject`) computed by `TagMatcher` is not currently branched on anywhere.

Note: the `arxiv` package is on v4, which removed `Search.results()` — use `Client().results(search)` (already fixed in `arxiv_fetcher.py`; watch for this again if the dependency is upgraded further).

**PDF parsing** (`pdf_pipeline.py`): PyMuPDF only, no GROBID — gives raw per-page text (no section/citation structure) plus embedded images with page/bbox. `_find_caption` locates a figure's caption by finding the nearest `Fig(ure)? N` text block below the image's bounding box on the same page. `pick_key_figure` scores each figure's caption by 4+ letter word overlap against the generator's draft text and picks the best match — this runs *after* generation, not during parsing, since it needs the draft to compare against. GROBID is a deliberate deferral, not an oversight: revisit only if citation-graph or clean section boundaries become worth the added ops (self-hosting a Java service) — see the note at the top of `pdf_pipeline.py`.

**LLM wiring** (`llm_client.py`): `TACCClient` wraps the `openai` SDK pointed at TACC's OpenAI-compatible endpoint (`config.yaml`'s `tacc.base_url` + `/v1`). `ModelRotator` round-robins through `tacc.models`, returning `(generator, verifier)` pairs with a hard guarantee `verifier != generator` for a given paper — this is intentional model diversity, not random selection, so the verifier doesn't share blind spots with whichever model wrote the draft. Which two models were used is recorded per-paper in the `papers` table (`generator_model`, `verifier_model`) for traceability back to a specific pairing if quality regresses.

`verify()` asks for strict JSON (`{"passed": bool, "notes": str}`) but models sometimes emit literal newlines inside the `notes` string, which breaks `json.loads` — there's a regex fallback that extracts `passed`/`notes` directly rather than repairing the JSON. If you see verification results with garbled notes, check this fallback path first before assuming the verifier logic is wrong.

The verifier has proven strict on rounding (e.g. flags "62.9s" summarized as "~63s" as an inaccuracy) — this is a prompt-tuning question, not fixed as of this writing; expect a nontrivial false-reject rate on otherwise-accurate summaries until the verifier prompt is loosened to tolerate reasonable rounding.

`embed()` calls `tacc.embedding_model` (`E5-Mistral-7B-Instruct`, 4096-dim) on `/v1/embeddings` — this is a separate, non-chat model; do not add it to the `models` rotation list for generate/verify.

**Storage** (`db.py`): SQLite is the single source of truth. `papers_fts` is an FTS5 external-content table over `title`/`abstract`/`draft`, kept in sync via `AFTER INSERT/UPDATE/DELETE` triggers on `papers` — if you ever bulk-modify `papers` outside `upsert_paper` (e.g. a raw `UPDATE`), the triggers still fire since they're on the table itself, but don't bypass them with `INSERT OR REPLACE ... content=off` tricks or the FTS index will silently drift. `embedding` is stored as a raw `array('f', ...).tobytes()` BLOB (native float32), not JSON — unpack with `array('f', blob)`.

**Rendering** (`render.py`): writes Jekyll-frontmattered Markdown to `docs/papers/<arxiv_id>.md` for GitHub Pages, copying the chosen figure into `docs/assets/figures/`. Only called for papers that pass verification.

**Semantic search export** (`export_vectors.py`): quantizes verified papers' embeddings to int8 (assumes roughly `[-1, 1]` range, single global scale factor) and writes `docs/search/vectors.bin` + `ids.json`. This only prepares the static data — actual query-time embedding requires a small external piece (a Cloudflare Worker or similar) holding the TACC key server-side, since the key can't live in a static site; that piece is not implemented in this repo (see the plan doc referenced below).

## Design decisions not obvious from the code

- **No CrewAI**: the original design used two CrewAI agents against Ollama. Both are gone — Ollama isn't available in this environment, and CrewAI added no value once the workflow is two flat sequential API calls (generate, verify) rather than genuine multi-agent delegation. `pipeline.py` is a plain function-call pipeline.
- **Model rotation over a fixed pair**: deliberately rotates across 4 large models (`DeepSeek-V3.2`, `Mistral-Large-3-675B-Instruct-2512`, `Qwen3-235B-A22B-Instruct-2507`, `gpt-oss-120b` as of this writing) rather than a fixed generator/verifier pair, to avoid one model's blind spots becoming permanent and to spread load on the shared TACC endpoint. Check `tacc.models` in `config.yaml` for the current live set — TACC's available models change (e.g. `Llama-4-Maverick-17B-128E-Instruct` was listed but returned 503 as of 2026-09-15).
- **PyMuPDF over GROBID**: see `pdf_pipeline.py` note above — explicit scope-limiting decision, not a missing feature.
- Full architecture/staging plan lives at `~/.claude/plans/lexical-doodling-meerkat.md` (not in this repo) if deeper rationale on the site/distribution pieces (Pagefind, email digest, Cloudflare Worker) is needed.
