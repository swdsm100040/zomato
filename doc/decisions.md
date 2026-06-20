# Implementation decisions

## Phase 0 — Runtime and tooling

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Matches Hugging Face `datasets` ecosystem for Phase 1 ingestion; stdlib `tomllib` for config. |
| Packaging | `pyproject.toml` + setuptools, `src/` layout | Standard editable installs; clear package boundary for later FastAPI (Phase 4). |
| LLM integration (planned) | OpenAI-compatible HTTPS API | Single contract (`LLM_API_KEY`, optional `LLM_BASE_URL`, `LLM_MODEL`) covers OpenAI and many gateways; adapter in Phase 3. |
| Config files | `config/app.toml` + JSON mapping stub | TOML for app/dataset/budget; JSON for mapping until Phase 1 may introduce YAML if preferred. |
| CLI | `zomato-recsys` entry point | Health/version without starting a server; `ingest` loads the catalog (Phase 1); `filter` runs Phase 2; `groq-complete` runs Phase 3 (Groq) with optional `--print-prompt`. |

## Phase 1 — Ingestion and catalog

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hub loader | `datasets.load_dataset` | Matches architecture §4.1; supports `revision` and split slicing for tests. |
| `restaurant_id` | `rec-` + SHA-256 hex of UTF-8 fingerprint | Fingerprint = normalized `name`, `city` (fallback `Unknown`), `area`, `address`, `url`, joined by `\\x1f`. **Disambiguator** suffix `\\x1f{n}` appended before hash if duplicate fingerprints appear (extremely rare). |
| Canonical city | `listed_in(city)` | Aligns user “Bangalore / Delhi” style filters with dataset metro field; `location` is neighborhood (`area`). |
| Catalog store | `InMemoryCatalog` | Phase 1 scope; swap for SQLite/Parquet later if needed. |
| Row drops | Rows with empty `name` after trim | Keeps catalog display-safe per edge-case catalog (docs/edgecase.md). |

## Phase 2 — Filter engine

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Budget mapping | **`fixed_bands`** in `config/app.toml` | INR-style `low_max` / `medium_max` on `cost_for_two`; `policy = unconfigured` skips budget hard filter. Percentile-based bands remain a future option. |
| Null rating | If `min_rating > 0`, exclude `aggregate_rating is None`; if `min_rating <= 0`, allow nulls through the rating filter | Documented in `filters/engine.py` module docstring (edgecase.md §C). |
| Location | Case-insensitive match: needle in city/area, city/area in needle, or needle in combined haystack | Covers “Bangalore” and neighborhood substrings without a separate allowlist file for MVP. |
| Cuisine filter | User list empty → any; else **any-of** intersection with restaurant cuisine tokens (already lowercased in Phase 1). | Matches architecture §4.3. |
| Heuristic + cap | Sort by `(-cuisine_overlap, -rating, cost_distance_to_band_midpoint, restaurant_id)` then cap at `[filter] candidate_cap` | Deterministic tie-break; `capped_to` in `CandidateSet` is the cap value when truncation happens, else `None`. |

## Phase 3 — Groq LLM adapter

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Provider | **Groq** OpenAI-compatible Chat Completions | Fast inference; single `POST .../v1/chat/completions` via HTTPX; documented in architecture §4.5. |
| Auth | `GROQ_API_KEY` primary; fallback `LLM_API_KEY` for migration | Matches `.env.example` and `load_groq_settings`. |
| Structured output | Request `response_format: json_object` when `[groq] use_json_object` / `GROQ_JSON_OBJECT` true | Encourages parseable payloads; parser still validates schema. |
| Prompt injection | Collapse whitespace/newlines and cap `free_text` (`max_free_text_chars`); system rules tell model to ignore conflicting user text | Architecture §7. |
| Client | `GroqChatClient` with injectable `httpx.Client` | Unit tests use `MockTransport` without network. |
