# Problem statement: AI-assisted restaurant discovery (Zomato-inspired)

## Project context

This repository is a **learning project** that explores how to combine **structured restaurant data** with a **large language model (LLM)** to produce recommendations similar in spirit to discovery experiences on platforms like Zomato—where users care about location, price, cuisine, ratings, and softer preferences (occasion, atmosphere, dietary needs).

The codebase is expected to grow around this document: the problem statement is the **single source of truth** for what we are building, why it matters, and how we will validate success.

## Problem we are solving

Restaurant catalogs are large and noisy. Users rarely want “any” highly rated place; they want options that **fit constraints** (where they are, what they can spend, what they feel like eating) and **clear rationale** so they can choose quickly. Pure keyword search or rigid filters alone often feel mechanical; pure LLM answers without grounding can hallucinate venues or ignore hard constraints.

We aim to solve **grounded, personalized shortlisting**:

1. **Grounding**: Recommendations must come from a **real dataset** of restaurants with verifiable fields (name, location, cuisines, cost, ratings, etc.).
2. **Personalization**: User preferences (explicit and optional natural-language hints) should **drive filtering and ranking**.
3. **Explainability**: The system should articulate **why** each option fits, in natural language, without inventing facts not supported by the data passed to the model.

## Objectives

Design and implement a service (or app) that:

- Accepts **structured preferences** (e.g., city/area, budget band, cuisines, minimum rating) and optional **free-text** preferences (e.g., family-friendly, quick lunch, date night).
- Loads and preprocesses a **real-world restaurant dataset** (see [Data source](#data-source)).
- **Filters** the catalog to a relevant candidate set, then uses an **LLM** to **rank** and **explain** the top choices.
- **Presents** results in a clear, scannable format for end users.

## Why this approach

| Piece | Role |
|--------|------|
| Structured data + rules/filters | Enforce hard constraints (location, budget, rating floor) and shrink the search space. |
| LLM | Turn a small set of candidates into a **sorted, human-readable** list with **short explanations** and optional summary copy. |

This hybrid design balances **factual grounding** with **flexible reasoning** over user intent.

## System workflow

### 1. Data ingestion

- Load and preprocess the Zomato-style restaurant dataset from Hugging Face: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation).
- Normalize and retain fields needed for filtering and display (e.g., restaurant name, location, cuisines, cost/for-two, aggregate rating, and any other columns useful for prompts).

### 2. User input

Collect preferences such as:

- **Location** (e.g., Delhi, Bangalore).
- **Budget** (e.g., low / medium / high, or numeric bands aligned to the dataset).
- **Cuisine** (e.g., Italian, Chinese).
- **Minimum rating**.
- **Additional preferences** (e.g., family-friendly, quick service)—via structured fields and/or natural language.

### 3. Integration layer

- Filter and prepare a **candidate set** from the dataset based on user input.
- Serialize the candidates (tabular or JSON) for the LLM.
- Design a **prompt** that instructs the model to: only discuss restaurants from the provided list, respect user constraints, rank, and justify each pick without fabricating attributes not present in the input.

### 4. Recommendation engine

Use the LLM to:

- **Rank** restaurants within the candidate set.
- **Explain** why each recommendation fits the user.
- Optionally **summarize** the slate of choices in one short paragraph.

### 5. Output display

Present top recommendations in a user-friendly format, including at minimum:

- Restaurant name  
- Cuisine(s)  
- Rating  
- Estimated cost (or dataset-equivalent)  
- **AI-generated explanation** tied to the provided fields  

## Data source

- **Dataset**: [Hugging Face — ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)  
- **Use**: Offline or programmatic loading for ingestion, preprocessing, and candidate retrieval. Licensing and attribution should follow the dataset card when shipping or publishing derivative work.

## Scope and non-goals

**In scope**

- End-to-end flow from dataset → preferences → filtered candidates → LLM ranking/explanation → UI or API response.
- Prompt design, evaluation of recommendation quality on sample personas, and basic guardrails (e.g., “only use provided restaurants”).

**Out of scope (unless explicitly added later)**

- Real-time Zomato production APIs, payments, or live order tracking.
- Training a custom embedding or ranking model from scratch (optional future work; initial version may use filters + LLM only).

## Success criteria

- Users receive **only** restaurants that exist in the dataset among the filtered candidates (no invented venues in the structured output).
- Top results **respect** stated hard constraints (location, budget, minimum rating) when those fields exist in the data.
- Explanations are **consistent** with the attributes supplied to the model and read as helpful, not generic boilerplate.
- The system is **repeatable**: same inputs and data snapshot yield deterministic filtering; LLM outputs may vary but should remain on-policy.

## Open decisions (to resolve during implementation)

**Resolved in Phase 0–2** (see [docs/decisions.md](./decisions.md), [README.md](../README.md)):

- **Runtime stack:** Python 3.11+, `pyproject.toml` / setuptools, `src/` package layout; CLI entry point `zomato-recsys` for health/version/ingest/**filter** (demo). HTTP service deferred to Phase 4.
- **LLM provider:** **Groq** (OpenAI-compatible Chat Completions). Environment variables `GROQ_API_KEY` (or transitional `LLM_API_KEY`), optional `GROQ_BASE_URL`, `GROQ_MODEL`, and `[groq]` in `config/app.toml` (see `.env.example` and architecture §8). Ranking/explanation adapter lives in `src/zomato_recsys/llm/`.
- **Dataset revision pin:** `config/app.toml` pins a Hugging Face git revision for reproducible loads.
- **Column mapping:** `config/column_mapping.json` maps canonical `Restaurant` fields to Hub columns for the `train` split (see [docs/architecture.md](./architecture.md) §5).
- **Budget → cost mapping (MVP):** `fixed_bands` in `config/app.toml` (`low_max`, `medium_max`, `[filter] candidate_cap`). See [docs/decisions.md](./decisions.md) Phase 2.

**Optional later improvements:**

- Percentile-based budget bins computed at ingest time (distribution-aware bands).

---

*This document should be updated as implementation choices are made so the repository always reflects the intended problem and boundaries of the project.*
