"""
Download and parse an arXiv PDF: full text for claim verification,
embedded figures with their nearby captions for the astrobites-style
key-figure pick.

No GROBID: PyMuPDF gives raw per-page text (no section/citation
structure), which is fine for "does this claim appear in the paper"
verification. Revisit if citation-graph or clean section boundaries
become worth the added ops (see CLAUDE.md plan notes).
"""

import re
import requests
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List


CAPTION_PATTERN = re.compile(r"^\s*(Fig(?:ure)?\.?\s*\d+)", re.IGNORECASE)


def download_pdf(arxiv_id: str, pdf_url: str, cache_dir: Path) -> Path:
    """Download the PDF to cache_dir, skip if already present."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = cache_dir / f"{arxiv_id}.pdf"
    if pdf_path.exists():
        return pdf_path

    response = requests.get(pdf_url, timeout=60)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    return pdf_path


def _find_caption(page: fitz.Page, image_bbox: fitz.Rect) -> str:
    """
    Find the text block most likely to be this image's caption.
    Captions in astro-ph papers are almost always the nearest text block
    below the figure that starts with "Figure N" / "Fig. N".
    """
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
    candidates = []
    for b in blocks:
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        if y0 < image_bbox.y1:
            continue  # block is above the image, captions are below
        if CAPTION_PATTERN.match(text.strip()):
            distance = y0 - image_bbox.y1
            candidates.append((distance, text.strip()))

    if not candidates:
        return ""
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


def extract_paper(pdf_path: Path, image_dir: Path) -> Dict:
    """
    Extract full text and figures (with captions) from a PDF.

    Returns:
        {
            'full_text': str,
            'figures': [{'path': str, 'caption': str, 'page': int}, ...]
        }
    """
    image_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)

    full_text_parts = []
    figures = []
    arxiv_stem = pdf_path.stem

    for page_num, page in enumerate(doc):
        full_text_parts.append(page.get_text())

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            bbox = rects[0]

            # Skip tiny images (logos, icons, decorative rules) - not real figures
            if bbox.width < 100 or bbox.height < 100:
                continue

            caption = _find_caption(page, bbox)

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue
            ext = base_image["ext"]
            image_bytes = base_image["image"]

            image_filename = f"{arxiv_stem}_p{page_num}_{img_index}.{ext}"
            image_path = image_dir / image_filename
            image_path.write_bytes(image_bytes)

            figures.append({
                "path": str(image_path),
                "caption": caption,
                "page": page_num,
            })

    doc.close()

    return {
        "full_text": "\n".join(full_text_parts),
        "figures": figures,
    }


def pick_key_figure(figures: List[Dict], key_results_text: str) -> Dict:
    """
    Pick the figure whose caption has the most keyword overlap with the
    generator's key-results text. Returns {} if no figures or no overlap.
    """
    if not figures:
        return {}

    key_words = set(re.findall(r"\b\w{4,}\b", key_results_text.lower()))
    if not key_words:
        return figures[0]

    best_figure = {}
    best_score = -1
    for fig in figures:
        caption_words = set(re.findall(r"\b\w{4,}\b", fig["caption"].lower()))
        score = len(key_words & caption_words)
        if score > best_score:
            best_score = score
            best_figure = fig

    return best_figure if best_score > 0 else figures[0]


def process_paper(arxiv_id: str, pdf_url: str, cache_dir: str = "./arxiv_cache") -> Dict:
    """Convenience entry point: download + extract for one paper."""
    cache_path = Path(cache_dir)
    pdf_path = download_pdf(arxiv_id, pdf_url, cache_path / "pdfs")
    return extract_paper(pdf_path, cache_path / "figures")


if __name__ == "__main__":
    # Manual smoke test against a real paper fetched earlier in the session.
    import json

    result = process_paper(
        "2609.17382v1",
        "https://arxiv.org/pdf/2609.17382v1",
    )
    print(f"Full text: {len(result['full_text'])} chars")
    print(f"Figures found: {len(result['figures'])}")
    for fig in result["figures"]:
        print(f"  {fig['path']}")
        print(f"    caption: {fig['caption'][:80]!r}")
