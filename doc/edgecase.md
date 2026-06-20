# Edge cases and failure modes

This catalog complements [architecture.md](./architecture.md) (guardrails, components, data model) and [implementation-plan.md](./implementation-plan.md) (phases). Use it when writing tests and acceptance checks. Per-phase **evaluation checklists** live under [docs/eval/](./eval/).

---

## How to use this document

| Column / idea | Meaning |
|---------------|---------|
| **Where** | Architectural area (see architecture §4–§7). |
| **When** | Input or environment condition. |
| **Expected** | Correct behavior; tie to tests where obvious. |
| **Phase** | First phase that should handle or document the case ([implementation-plan](./implementation-plan.md)). |

---

## A. Foundations and configuration (Phase 0)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| Config | Missing `LLM_API_KEY` at runtime (only needed when calling LLM) | Clear error when LLM path invoked; ingestion may still run if key not required for load. | 0 / 4 |
| Config | Invalid dataset revision pin (typo or removed revision) | Fail fast with actionable message; do not silently fall back to “latest” unless explicitly documented. | 0 / 1 |
| Config | Mapping file path points to missing file | Documented default or explicit error at startup/ingest. | 0 / 1 |
| Secrets | `.env` committed by mistake | `.gitignore` excludes `.env`; docs only reference `.env.example`. | 0 |

---

## B. Ingestion and catalog (Phase 1)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| HF Hub | Network offline or rate limited | Retry/backoff or clear failure; partial cache behavior documented. | 1 |
| HF Hub | Dataset schema changes (new/renamed columns) | Mapping config fails visibly or maps with warnings; ingestion metrics report unmapped columns. | 1 |
| Raw row | Missing name or all display-critical fields | Row dropped or quarantined; counted in `dropped_rows` or warnings. | 1 |
| Raw row | Malformed numeric rating or cost (`"N/A"`, empty string) | Parsed as null per policy; does not crash ingest. | 1 |
| Raw row | Extreme string length in text columns | Truncation at ingest or cap with metric; no unbounded memory. | 1 |
| Raw row | Duplicate logical restaurants (same name + location) | Stable `restaurant_id` still unique (strategy documented); no silent merge unless intentional. | 1 |
| Canonical | `cuisines` empty after split | Restaurant still loadable; filter behavior defined (match “any” vs. exclude). | 1 / 2 |
| Catalog | `get_restaurant_by_id` unknown ID | Returns null/Option.none; callers handle. | 1 / 4 |
| IDs | Re-ingest with same revision but different row order | If ID strategy is “sorted index,” order must be deterministic before assign (architecture §4.1). | 1 |

---

## C. Filter engine and preferences (Phase 2)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| Location | User city casing/spacing differs from dataset (`"delhi"` vs `"Delhi"`) | Normalization policy yields matches or documented non-match. | 2 |
| Location | User enters suburb; dataset only has metro name | Document match rules; may return empty—message should not blame user opaquely. | 2 |
| Location | Empty location string | Validation error or “match all” policy—must be explicit, not accidental full scan for MVP unless intended. | 2 / 4 |
| Rating | `min_rating` higher than any restaurant in city | Zero candidates; no LLM call (architecture §4.7, sequence diagram). | 2 / 4 |
| Rating | Restaurant `aggregate_rating` is null | Follow documented null policy (exclude vs. include). | 2 |
| Cuisine | User lists multiple cuisines (AND vs OR) | Document semantics (typically OR for “any of these”). | 2 |
| Cuisine | User cuisine not in dataset vocabulary | Zero or partial matches; no crash. | 2 |
| Cuisine | Empty `cuisines` in preferences | Means “any cuisine” if documented. | 2 |
| Budget | User band maps to empty numeric range (misconfigured percentiles) | Safe fallback or error at config load; never “all pass.” | 2 |
| Budget | Restaurant cost null | Document: exclude from budget filter vs. treat as unknown bucket. | 2 |
| Cap | Hard filters yield 10,000 rows; cap is 50 | Deterministic top-50 per documented heuristic; `capped_to` in metadata. | 2 |
| Cap | Tie scores in pre-rank | Stable tie-break (e.g., sort by `restaurant_id`). | 2 |
| Prefs | `top_k` larger than candidate count | Return all candidates to LLM or cap to count; response length policy documented. | 2 / 4 |
| Prefs | Negative or zero `top_k` | API validation rejects or clamps with error. | 4 |

---

## D. Prompt builder and LLM adapter (Phase 3)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| Prompt | Very long `free_text` (injection or paste) | Length cap; model instructed to ignore conflicting instructions (architecture §7). | 3 / 6 |
| Prompt | `free_text` contains JSON/markdown delimiters | Escaping or framing so system message boundaries stay intact. | 3 |
| Prompt | Candidate serialization near context limit | Truncation per restaurant fields; all IDs still present or documented subset rule. | 3 |
| Prompt | Zero candidates (should not happen if orchestrator correct) | Orchestrator must not call LLM; if called, adapter should no-op or error. | 3 / 4 |
| LLM API | 401/403 invalid key | Structured error; no key in logs. | 3 / 6 |
| LLM API | 429 rate limit | Bounded retries with backoff; total deadline respected. | 3 / 6 |
| LLM API | 5xx or timeout | Same; user-facing message after exhaustion. | 3 / 6 |
| LLM API | Empty response body | Parse error path; no partial UI from garbage. | 3 |
| Parse | Model returns valid JSON but wrong shape (missing `rank`) | Validator or parse layer rejects with repair/retry policy per architecture §7. | 3 / 4 |
| Parse | Model returns prose only | JSON parse failure; documented retry or error. | 3 / 4 |
| Parse | UTF-8 mojibake or special characters in explanations | Still parseable JSON; display safe in UI. | 3 / 5 |

---

## E. Orchestrator, validator, API (Phase 4)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| Orchestrator | Catalog empty (ingest failed) | Recommend endpoint fails clearly; not “empty recommendations” silently. | 4 |
| Validator | LLM returns `restaurant_id` not in candidate batch | Drop invalid IDs; metrics `validation_drops`; optional repair pass (architecture §7). | 4 / 6 |
| Validator | Duplicate same ID twice in model output | Dedupe policy: first rank wins or lowest rank wins—documented. | 4 |
| Validator | Non-contiguous ranks (1, 5, 7) | Sort by rank; display order consistent. | 4 |
| Validator | LLM “hallucinated” rating in explanation only | UI still shows catalog rating/cost only (architecture §4.6, §7). | 4 / 5 |
| API | Malformed JSON body | 400 with stable error code/schema. | 4 |
| API | Unknown extra fields in body | Ignore or reject per API contract—documented. | 4 |
| API | Concurrent requests | No global mutable filter state; catalog read-only after load. | 4 |
| API | Very large `top_k` abuse | Max cap server-side. | 4 / 6 |

---

## F. Presentation and client (Phase 5)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| UI | Slow LLM (30s+) | Loading indicator; no double-submit or cancel policy if supported. | 5 |
| UI | Empty results | Dedicated empty state copy; no blank screen. | 5 |
| UI | Partial network failure mid-request | Error message; retry affordance optional. | 5 |
| UI | Explanation contains HTML-like strings | Render as text; XSS-safe rendering in web apps. | 5 |
| UI | Screen reader / keyboard | Forms labeled; focus order sensible (if web). | 5 |
| CLI | Narrow terminal width | Table still readable or wrapped without data loss. | 5 |

---

## G. Hardening and observability (Phase 6)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| Logs | Debug mode logs full prompt | Production flag disables or redacts PII and keys (architecture §9). | 6 |
| Metrics | High `validation_drops` after deploy | Observable spike; runbook suggests prompt/schema check. | 6 |
| Rate limit | Client spams `/recommendations` | 429 or throttle; no thread exhaustion. | 6 |

---

## H. CI, packaging, and operations (Phase 7)

| Where | When | Expected | Phase |
|-------|------|----------|-------|
| CI | No network in sandbox | Tests use fixtures; cached dataset or skip documented. | 7 |
| Docker | Read-only filesystem except cache | HF cache volume or env documented; clear error if cache not writable. | 7 |
| License | Redistributing derived dataset snapshot | README points to dataset card and terms (problem statement data source). | 7 |

---

## Cross-phase regression triggers

Run a **smoke subset** after changes in:

- **Mapping or normalize** → re-run ingestion golden tests + filter boundary tests.
- **Filter logic** → re-run zero-candidate and cap tests + one orchestrator integration test.
- **Prompt or schema** → re-run validator fixtures + one live LLM smoke (manual) if keys available.

---

## Related documents

| Document | Role |
|----------|------|
| [problemStatement.md](./problemStatement.md) | Success criteria and scope |
| [architecture.md](./architecture.md) | Guardrails §7, testing §11, sequence §6 |
| [implementation-plan.md](./implementation-plan.md) | Phase boundaries |
| [docs/eval/phase-0.md](./eval/phase-0.md) … [phase-7.md](./eval/phase-7.md) | Phase evaluation criteria |

---

*Add rows as new risks appear (new fields, new LLM provider, new UI surface).*
