/**
 * Minimal stateless proxy: takes a search query, embeds it via TACC's
 * E5-Mistral-7B-Instruct model, returns the vector. This is the only
 * server-side piece in the whole site - the TACC key can't live in a
 * static GitHub Pages site, so it lives here instead, in an env var
 * (set with `wrangler secret put TACC_API_KEY`, never in this file or
 * wrangler.toml).
 *
 * Deploy: cd cloudflare-worker && wrangler deploy
 * Then update WORKER_URL in docs/assets/js/semantic-search.js.
 */

const TACC_BASE_URL = "https://ai.tejas.tacc.utexas.edu";
const EMBEDDING_MODEL = "E5-Mistral-7B-Instruct";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let query;
    try {
      ({ query } = await request.json());
    } catch {
      return new Response("Invalid JSON body", { status: 400 });
    }
    if (!query || typeof query !== "string") {
      return new Response("Missing 'query' string", { status: 400 });
    }

    const response = await fetch(`${TACC_BASE_URL}/v1/embeddings`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.TACC_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ model: EMBEDDING_MODEL, input: query.slice(0, 8000) }),
    });

    if (!response.ok) {
      const text = await response.text();
      return new Response(`TACC embedding failed: ${text}`, { status: 502 });
    }

    const data = await response.json();
    const embedding = data.data[0].embedding;

    return new Response(JSON.stringify({ embedding }), {
      headers: {
        "Content-Type": "application/json",
        // Static site origin only - tighten to your actual Pages domain.
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};
