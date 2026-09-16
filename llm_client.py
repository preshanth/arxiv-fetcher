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
        return response.choices[0].message.content.strip()

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
            "passed=false if the summary states anything not supported by the "
            "paper text, or misrepresents a result. The notes field MUST be a "
            "single line: no literal newlines inside the string, use ' | ' to "
            "separate multiple issues instead."
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
