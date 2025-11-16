// ESM, Node 18+ (global fetch)
const WIKI_UA = process.env.WIKI_UA || "AIHubBot/1.1 (contact: you@example.com)";

export async function wikiTitleSearch(title) {
  const q = encodeURIComponent(title);
  const url = `https://api.wikimedia.org/core/v1/wikipedia/en/search/title?q=${q}&limit=1`;
  const r = await fetch(url, { headers: { "Api-User-Agent": WIKI_UA } });
  if (!r.ok) throw new Error(`Wiki title search ${r.status}`);
  const json = await r.json();
  return json?.pages?.[0] || null;
}

export async function wikiSummary(titleOrKey) {
  const key = encodeURIComponent(titleOrKey);
  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${key}`;
  const r = await fetch(url, { headers: { "Api-User-Agent": WIKI_UA } });
  if (!r.ok) throw new Error(`Wiki summary ${r.status}`);
  const j = await r.json();
  return {
    title: j.title,
    description: j.description,
    extract: j.extract,
    url: j?.content_urls?.desktop?.page || `https://en.wikipedia.org/wiki/${key}`,
  };
}
