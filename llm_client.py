"""
Thin wrapper over TACC's OpenAI-compatible inference endpoint.
Handles model rotation (generator != verifier per paper) and the three
roles the pipeline needs: generate, verify, embed.
"""

import os
import re
import json
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, List

load_dotenv()


class ModelRotator:
    """Round-robins through a model pool, guaranteeing verifier != generator."""

    def __init__(self, models: List[str]):
        if len(models) < 2:
            raise ValueError("Need at least 2 models to rotate generator/verifier")
        self.models = models
        self._i = 0

    def next_pair(self) -> tuple:
        n = len(self.models)
        generator = self.models[self._i % n]
        verifier = self.models[(self._i + 1) % n]
        self._i += 1
        return generator, verifier


class TACCClient:
    """Generate, verify, and embed against TACC's OpenAI-compatible endpoint."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        tacc_config = config["tacc"]
        api_key = os.environ.get(tacc_config["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Environment variable {tacc_config['api_key_env']} is not set")

        self.client = OpenAI(base_url=f"{tacc_config['base_url']}/v1", api_key=api_key)
        self.embedding_model = tacc_config["embedding_model"]
        self.temperature = tacc_config.get("temperature", 0.2)
        self.max_tokens = tacc_config.get("max_tokens", 4096)
        self.rotator = ModelRotator(tacc_config["models"])

        self.tag_vocabulary = sorted({
            tag for tags in config["active_tags"].values() if isinstance(tags, list)
            for tag in tags
        })

    def _chat(self, model: str, system: str, user: str, max_tokens: int = None) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            # Reasoning models (e.g. gpt-oss-120b) can spend the whole
            # max_tokens budget on hidden reasoning tokens before emitting
            # any content, leaving content=None with finish_reason='length'.
            finish_reason = response.choices[0].finish_reason
            raise RuntimeError(
                f"{model} returned empty content (finish_reason={finish_reason}) - "
                f"likely exhausted max_tokens on reasoning before producing output"
            )
        return content.strip()

    def generate(self, paper: Dict, full_text: str, model: str) -> str:
        """
        Astrobites-style summary: accessible, active voice, "why this matters"
        framing, grounded in the full paper text (not just the abstract).
        """
        system = (
            "You are an astronomy writer in the style of Astrobites: you turn "
            "technical papers into summaries a broad astronomy-literate audience "
            "can follow, without dumbing down the science. Use plain, active-voice "
            "language. Explain why the result matters before diving into how it "
            "was done. Stay grounded strictly in the paper text provided - do not "
            "invent results, numbers, or claims not present in the text."
        )
        # Full text can be long; truncate defensively to keep prompt size sane.
        truncated_text = full_text[:40000]
        user = f"""Title: {paper['title']}
Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}
arXiv ID: {paper['arxiv_id']}

Full paper text:
{truncated_text}

Write an Astrobites-style summary with these sections:

## Why This Matters
## What They Did
## Key Results
## What's Next

Keep it under 500 words total. Be specific about instruments, facilities, and quantitative results actually stated in the text."""
        return self._chat(model, system, user)

    def verify(self, draft: str, full_text: str, model: str) -> Dict:
        """
        Fact-check the draft's claims against the actual paper text.
        Returns {'passed': bool, 'notes': str}.
        """
        system = (
            "You are a fact-checker for astronomy summaries. You are given a "
            "summary and the full text of the paper it claims to describe. "
            "Check every factual claim, number, and attribution in the summary "
            "against the paper text. Respond ONLY with JSON: "
            '{"passed": true/false, "notes": "explanation"}. '
            "\n\nTolerate reasonable rounding and approximation: '~63s' for "
            "62.9s, '~7km' for 7.3km, or 'about 0.99 AUC' for 0.992 are "
            "CORRECT, not errors - do not fail the summary for these. Also "
            "tolerate paraphrasing that preserves meaning (e.g. summarizing "
            "a citation without repeating its exact year format). "
            "\n\nOnly set passed=false if the summary states a claim, number, "
            "or attribution that is materially wrong - i.e. a reader would "
            "draw a different conclusion about the paper's findings, methods, "
            "or magnitude of a result than they would from the paper itself. "
            "Order-of-magnitude, direction of an effect, and which "
            "instrument/method was used are the things that matter; the "
            "second significant figure of a stated number does not. "
            "\n\nThe notes field MUST be a single line: no literal newlines "
            "inside the string, use ' | ' to separate multiple issues instead."
        )
        truncated_text = full_text[:40000]
        user = f"""Paper text:
{truncated_text}

Summary to verify:
{draft}

Respond with JSON only."""
        raw = self._chat(model, system, user, max_tokens=2048)
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Some models emit literal newlines inside string values despite
            # instructions, which breaks strict JSON parsing. Fall back to
            # pulling the two fields out directly rather than repairing JSON.
            passed_match = re.search(r'"passed"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
            notes_match = re.search(r'"notes"\s*:\s*"(.*)"\s*}?\s*$', cleaned, re.DOTALL)
            if passed_match:
                notes = notes_match.group(1).replace("\n", " ").strip() if notes_match else raw[:300]
                return {"passed": passed_match.group(1).lower() == "true", "notes": notes}
            return {"passed": False, "notes": f"Verifier returned unparseable output: {raw[:300]}"}

    def revise(self, draft: str, full_text: str, verify_notes: str, model: str) -> str:
        """
        Ask the generator to correct a draft based on the verifier's specific
        objections, grounded back in the full paper text (not just patching
        the flagged sentence blind).
        """
        system = (
            "You are an astronomy writer revising a summary that a fact-checker "
            "flagged issues in. Fix ONLY the specific issues listed - do not "
            "rewrite unrelated parts of the summary. Stay grounded strictly in "
            "the paper text provided. Keep the same section structure and "
            "roughly the same length as the original draft."
        )
        truncated_text = full_text[:40000]
        user = f"""Paper text:
{truncated_text}

Original summary:
{draft}

Fact-checker's issues to fix:
{verify_notes}

Write the corrected summary."""
        return self._chat(model, system, user)

    def classify_tags(self, paper: Dict, model: str) -> List[str]:
        """
        Semantic tag assignment from the abstract, restricted to the
        controlled vocabulary in config.yaml's active_tags. This is the
        "smart" tagging layer for serving papers by interest - the keyword
        prefilter in tags.py decides accept/reject cheaply across the full
        daily arXiv volume, this runs only on papers that already passed
        that filter, and reads meaning rather than matching bare words (so
        it won't tag a chemistry "polarization" paper as radio polarimetry).
        """
        system = (
            "You classify astronomy paper abstracts against a fixed tag "
            "vocabulary. Read the title and abstract, then return ONLY the "
            "tags from the provided vocabulary that genuinely apply to this "
            "paper's actual topic - not tags that merely share a word with "
            "the abstract. Respond ONLY with a JSON array of strings, e.g. "
            '["vla", "calibration"]. Return an empty array [] if nothing in '
            "the vocabulary genuinely applies. Do not invent tags outside "
            "the given vocabulary."
        )
        user = f"""Vocabulary: {json.dumps(self.tag_vocabulary)}

Title: {paper['title']}
Abstract: {paper['abstract']}

Return the JSON array of applicable tags."""
        # 1024 not 256: reasoning models (gpt-oss-120b etc) spend tokens on
        # hidden reasoning before content, and 256 was observed to starve
        # the actual JSON output entirely on longer abstracts.
        raw = self._chat(model, system, user, max_tokens=1024)
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            tags = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            tags = json.loads(match.group(0)) if match else []

        vocabulary_set = set(self.tag_vocabulary)
        return [t for t in tags if t in vocabulary_set]

    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(model=self.embedding_model, input=text[:8000])
        return response.data[0].embedding


if __name__ == "__main__":
    # Smoke test against the paper already fetched/parsed earlier in the session.
    import json as json_module
    from pdf_pipeline import process_paper

    with open("arxiv_papers/papers_20260915.json") as f:
        papers = json_module.load(f)
    paper = next(p for p in papers if p["arxiv_id"] == "2609.17382v1")

    parsed = process_paper(paper["arxiv_id"], paper["pdf_url"])

    tacc = TACCClient()
    gen_model, ver_model = tacc.rotator.next_pair()
    print(f"Generator: {gen_model}, Verifier: {ver_model}")

    draft = tacc.generate(paper, parsed["full_text"], gen_model)
    print(f"\n--- DRAFT ({len(draft)} chars) ---\n{draft[:500]}...\n")

    result = tacc.verify(draft, parsed["full_text"], ver_model)
    print(f"--- VERIFICATION ---\n{result}\n")

    vec = tacc.embed(draft)
    print(f"--- EMBEDDING --- dims: {len(vec)}")
