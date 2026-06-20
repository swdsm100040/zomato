import pytest
from zomato_recsys.data.catalog import InMemoryCatalog
from zomato_recsys.data.models import UserPreferences
from zomato_recsys.llm.adapter import LLMResult
from zomato_recsys.orchestrator import run_recommendation

def test_run_recommendation_successful(monkeypatch, sample_restaurants):
    # Mock LLM complete method
    def mock_complete(self, messages):
        return LLMResult(
            content='{"summary": "Mock summary", "rankings": [{"restaurant_id": "rec-1", "rank": 1, "explanation": "Mock explanation"}]}',
            latency_ms=150.0
        )
    monkeypatch.setattr("zomato_recsys.llm.adapter.GroqChatClient.complete", mock_complete)
    
    catalog = InMemoryCatalog(sample_restaurants)
    filter_cfg = {"candidate_cap": 5, "null_rating_policy": "exclude"}
    groq_settings = {"model": "llama-mock", "api_key": "mock-key", "timeout_seconds": 10}
    
    # Request matching Koramangala (Jassi has rec-1)
    prefs = UserPreferences(
        location="Koramangala",
        top_k=1
    )
    
    response = run_recommendation(
        catalog=catalog,
        filter_cfg=filter_cfg,
        groq_settings=groq_settings,
        preferences=prefs,
        include_debug=True
    )
    
    assert response.summary == "Mock summary"
    assert len(response.items) == 1
    assert response.items[0].restaurant_id == "rec-1"
    assert response.items[0].explanation == "Mock explanation"
    assert response.items[0].backfilled is False
    
    assert response.debug is not None
    assert response.debug["llm_latency_ms"] > 0.0
    assert response.debug["candidates_sent_to_llm"] == 2 # Jassi and Black Pearl are in Koramangala

def test_run_recommendation_empty_early_exit(sample_restaurants):
    catalog = InMemoryCatalog(sample_restaurants)
    filter_cfg = {"candidate_cap": 5}
    groq_settings = {"model": "llama-mock"}
    
    # Non-existent location should exit early
    prefs = UserPreferences(
        location="Mars Colony",
        top_k=5
    )
    
    response = run_recommendation(
        catalog=catalog,
        filter_cfg=filter_cfg,
        groq_settings=groq_settings,
        preferences=prefs,
        include_debug=True
    )
    
    assert "No restaurants matched" in response.summary
    assert len(response.items) == 0
    assert response.debug["candidates_sent_to_llm"] == 0
    assert response.debug["llm_latency_ms"] == 0.0

def test_run_recommendation_llm_failure_fallback(monkeypatch, sample_restaurants):
    # Mock LLM complete returning error
    def mock_complete(self, messages):
        return LLMResult(
            content="",
            latency_ms=50.0,
            error="API Rate limit exceeded"
        )
    monkeypatch.setattr("zomato_recsys.llm.adapter.GroqChatClient.complete", mock_complete)
    
    catalog = InMemoryCatalog(sample_restaurants)
    filter_cfg = {"candidate_cap": 5}
    groq_settings = {"model": "llama-mock", "api_key": "mock-key"}
    
    prefs = UserPreferences(
        location="Koramangala",
        top_k=2
    )
    
    response = run_recommendation(
        catalog=catalog,
        filter_cfg=filter_cfg,
        groq_settings=groq_settings,
        preferences=prefs,
        include_debug=True
    )
    
    # Should fallback to deterministic backfill
    assert "Fallback" in response.summary or "fallback" in response.summary.lower()
    assert len(response.items) == 2
    assert response.items[0].backfilled is True
    assert response.items[1].backfilled is True
    assert response.debug["llm_error"] == "API Rate limit exceeded"
