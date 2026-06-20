import time
import logging
from typing import Dict, Any, Optional
from zomato_recsys.data.catalog import InMemoryCatalog
from zomato_recsys.data.models import UserPreferences
from zomato_recsys.filters.engine import apply_filters
from zomato_recsys.llm.prompts import build_prompt_messages
from zomato_recsys.llm.adapter import GroqChatClient, clean_json_fences
from zomato_recsys.validation.response import validate_and_merge, RecommendationResponse

logger = logging.getLogger(__name__)

def run_recommendation(
    catalog: InMemoryCatalog,
    filter_cfg: Dict[str, Any],
    groq_settings: Dict[str, Any],
    preferences: UserPreferences,
    include_debug: bool = False
) -> RecommendationResponse:
    """
    Orchestrate the end-to-end recommendation flow.
    1. Filter catalog based on hard constraints
    2. Check for empty candidate set (early exit)
    3. Construct system/user prompts
    4. Request rankings and explanations from Groq Chat API
    5. Validate and merge rankings with catalog data
    """
    start_time = time.time()
    
    # 1. Apply hard filters
    # We construct a configuration structure compatible with apply_filters
    app_cfg = {
        "filter": filter_cfg,
        "budget": {
            "fixed_bands": filter_cfg.get("fixed_bands", {
                "low_max": filter_cfg.get("low_max", 500),
                "medium_max": filter_cfg.get("medium_max", 1200)
            })
        }
    }
    
    candidate_set = apply_filters(catalog.get_all(), preferences, app_cfg)
    filter_latency = (time.time() - start_time) * 1000.0
    
    total_candidates = len(candidate_set.restaurants)
    
    # 2. Early exit if empty
    if total_candidates == 0:
        logger.info(f"Zero candidates matched filters for location={preferences.location}. Returning early.")
        debug_payload = None
        if include_debug:
            debug_payload = {
                "filter_latency_ms": filter_latency,
                "total_after_hard_filters": candidate_set.total_after_hard_filters,
                "capped_to": candidate_set.capped_to,
                "candidates_sent_to_llm": 0,
                "llm_latency_ms": 0.0,
                "validation_drops": 0,
                "llm_model": groq_settings.get("model")
            }
        return RecommendationResponse(
            summary=f"No restaurants matched your filters in {preferences.location}. Try broadening your search.",
            items=[],
            debug=debug_payload
        )
        
    # 3. Build prompt
    max_chars = int(groq_settings.get("max_free_text_chars", 500))
    messages = build_prompt_messages(preferences, candidate_set.restaurants, max_free_text_chars=max_chars)
    
    # 4. Invoke LLM
    llm_start = time.time()
    client = GroqChatClient(groq_settings)
    llm_result = client.complete(messages)
    llm_latency = (time.time() - llm_start) * 1000.0
    
    validation_drops = 0
    summary = None
    items = []
    
    # 5. Validate & Merge
    if not llm_result.error:
        cleaned_content = clean_json_fences(llm_result.content)
        items, summary, validation_drops = validate_and_merge(
            raw_json_str=cleaned_content,
            candidates=candidate_set.restaurants,
            prefs=preferences,
            backfill_allowed=True
        )
    else:
        logger.error(f"LLM request error: {llm_result.error}")
        # Default backfill: populate using pre-ranked items when LLM fails
        items, summary, validation_drops = validate_and_merge(
            raw_json_str="{}", # Forces standard backfill
            candidates=candidate_set.restaurants,
            prefs=preferences,
            backfill_allowed=True
        )
        if not summary:
            summary = f"LLM ranking failed: {llm_result.error}. Displaying fallback recommendations."
            
    total_latency = (time.time() - start_time) * 1000.0
    
    # Debug telemetry
    debug_payload = None
    if include_debug:
        debug_payload = {
            "filter_latency_ms": filter_latency,
            "total_after_hard_filters": candidate_set.total_after_hard_filters,
            "capped_to": candidate_set.capped_to,
            "candidates_sent_to_llm": total_candidates,
            "llm_latency_ms": llm_latency,
            "validation_drops": validation_drops,
            "llm_model": groq_settings.get("model"),
            "llm_error": llm_result.error,
            "total_latency_ms": total_latency
        }
        
    return RecommendationResponse(
        summary=summary,
        items=items,
        debug=debug_payload
    )
