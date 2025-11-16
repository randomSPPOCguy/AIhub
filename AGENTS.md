# Repository Guidelines

## Project Structure & Module Organization
AI Hub pairs a Node ingest/API server with optional ONNX helpers. Core runtime lives under `src/` where each folder mirrors a domain: `ingest/` for song-ended input, `routes/` and `proxy/` for HTTP/WebSocket endpoints, `services/` plus `harvest/` for metadata enrichment, `cli/` for the interactive `hub>` console, and `utils/` for diagnostics such as hardware detection. SQLite assets sit in `db/` (see `src/db/schema.sql`), while operational notes reside in `docs/`. `python_ai/` hosts the CUDA/ONNX sidecar and its `requirements.txt`. Model catalogs live under `models/` (drop overrides into `models/catalog.d/`). Reusable scripts stay in `bin/` and `scripts/`, and regression samples belong in `tests/`.

## Build, Test, and Development Commands
- `npm install` — install Node dependencies (Node 18+ required).
- `npm run migrate` — apply the SQLite schema via `src/db/migrate.js`.
- `npm run dev` — start the hub with watch mode for local iteration.
- `npm start` — launch the production server plus the CLI banner on the configured port.
- `npm run python-ai` or `python python_ai/server.py` — boot the ONNX Runtime bridge on :8000.
- `node bin/keygen.mjs -- --label qa` — mint an API key; store it once shown.
- `node bin/wd-artist-overview.mjs "Massive Attack"` — preview Wikidata/Discogs facts for validation.

## Coding Style & Naming Conventions
Use ES modules, 2-space indentation, and double quotes (see `src/index.js`). Favor `const`/`let`, camelCase identifiers, and small, single-purpose files with default exports for routers or proxies. Route handlers should validate inbound payloads with the local Zod schemas before touching services. Keep configuration reads centralized through `cfg` (see `src/config.js`) and never reach for `process.env` deep inside features. Console strings logged with the `[TAG]` pattern help operators filter output.

## Testing Guidelines
All JavaScript tests run directly with Node (e.g., `node tests/test_workflow.js`). Name new suites `test_<feature>.js` so readers can link them to the module they exercise. Use the provided fixtures (such as the Massive Attack payload in `tests/test_music_knowledge.js`) to stay within upstream rate limits. Record HTTP workflows in `tests/test.http` whenever you add a REST surface, and capture the CLI output or `curl` snippets inside your pull request description. Every new endpoint or enrichment path should include at least one happy-path script plus an error-path assertion.

## Commit & Pull Request Guidelines
Recent commits follow short, imperative summaries with optional prefixes (`chore: test commit`, `redux of AIhub`). Continue using that conventional-commit style (`type: scope`) so release notes remain parseable. Each pull request should include: a bullet summary, linked issue or ticket, configuration changes (referencing `docs/CONFIG_ENV.md`), screenshots or console transcripts for UI/CLI edits, and the exact commands used to test. Mention any ONNX/Python companion changes so reviewers spin up both services during verification.

## Security & Configuration Tips
Never commit `config.env`; duplicate `config.env.example` and follow `docs/CONFIG_ENV.md`. Store provider tokens and generated hub API keys in your local secret manager, not the repository. When working on new models, prefer `models/catalog.d/*.json` so you avoid modifying the tracked base catalog. Regenerate keys with `npm run keygen` if exposure is suspected, and audit the `/hub` endpoints with a key before merging network-facing changes.
