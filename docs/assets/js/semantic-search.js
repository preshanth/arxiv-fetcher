/*
 * Client-side semantic search. Fetches the precomputed, int8-quantized
 * paper vectors once, calls a small serverless Worker to embed the typed
 * query (the TACC key can't live in a static site), then ranks papers by
 * cosine similarity entirely in the browser.
 *
 * WORKER_URL must point at the deployed Cloudflare Worker (see
 * cloudflare-worker/embed-query.js) - this is a placeholder until deployed.
 */

const WORKER_URL = "https://REPLACE-WITH-YOUR-WORKER.workers.dev/embed";

let cachedVectors = null;
let cachedIds = null;

async function loadVectors() {
  if (cachedVectors && cachedIds) return { vectors: cachedVectors, ids: cachedIds };

  const [vectorsBuf, ids] = await Promise.all([
    fetch("/search/vectors.bin").then((r) => r.arrayBuffer()),
    fetch("/search/ids.json").then((r) => r.json()),
  ]);

  const dims = ids.dims;
  const raw = new Int8Array(vectorsBuf);
  const count = raw.length / dims;
  const vectors = [];
  for (let i = 0; i < count; i++) {
    vectors.push(raw.subarray(i * dims, (i + 1) * dims));
  }

  cachedVectors = vectors;
  cachedIds = ids;
  return { vectors, ids };
}

function cosineSimilarity(a, b) {
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB) + 1e-8);
}

async function semanticSearch(query, topK = 10) {
  const { vectors, ids } = await loadVectors();

  const response = await fetch(WORKER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) throw new Error(`Worker embed failed: ${response.status}`);
  const { embedding } = await response.json();

  const scale = ids.scale;
  const queryQuantized = embedding.map((v) => Math.max(-127, Math.min(127, Math.round(v * scale))));

  const scored = vectors.map((vec, i) => ({
    paper: ids.papers[i],
    score: cosineSimilarity(vec, queryQuantized),
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("semantic-search-form");
  const input = document.getElementById("semantic-search-input");
  const results = document.getElementById("semantic-search-results");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    results.innerHTML = "Searching...";
    try {
      const hits = await semanticSearch(input.value);
      results.innerHTML = hits
        .map(
          (h) =>
            `<li><a href="${h.paper.markdown_path.replace("docs/", "/")}">${h.paper.title}</a> (${h.score.toFixed(3)})</li>`
        )
        .join("");
    } catch (err) {
      results.innerHTML = `<li>Search failed: ${err.message}</li>`;
    }
  });
});
