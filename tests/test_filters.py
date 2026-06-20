import pytest
from zomato_recsys.data.models import UserPreferences, Restaurant
from zomato_recsys.filters.engine import (
    filter_by_location, 
    filter_by_rating, 
    filter_by_cuisine, 
    filter_by_budget, 
    apply_filters
)

def test_filter_by_location(sample_restaurants):
    # exact location match
    assert filter_by_location(sample_restaurants[0], "Koramangala 5th Block") is True
    # substring location match
    assert filter_by_location(sample_restaurants[0], "Koramangala") is True
    # case insensitivity match
    assert filter_by_location(sample_restaurants[0], "koramangala") is True
    # check no match
    assert filter_by_location(sample_restaurants[0], "Whitefield") is False
    # check empty loc
    assert filter_by_location(sample_restaurants[0], "") is True

def test_filter_by_rating(sample_restaurants):
    # Jassi De Paranthe (Rating 4.1)
    assert filter_by_rating(sample_restaurants[0], 4.0) is True
    assert filter_by_rating(sample_restaurants[0], 4.5) is False
    
    # New Restaurant (Rating None)
    # Policy: exclude when min_rating > 0
    assert filter_by_rating(sample_restaurants[4], 3.0, null_rating_policy="exclude") is False
    # Policy: include when min_rating <= 0
    assert filter_by_rating(sample_restaurants[4], 0.0, null_rating_policy="include") is True

def test_filter_by_cuisine(sample_restaurants):
    # Toit has cuisines ["italian", "american", "pizza"]
    assert filter_by_cuisine(sample_restaurants[3], ["Italian"]) is True
    assert filter_by_cuisine(sample_restaurants[3], ["pizza", "burger"]) is True
    assert filter_by_cuisine(sample_restaurants[3], ["chinese"]) is False
    # empty cuisine preference list
    assert filter_by_cuisine(sample_restaurants[3], []) is True

def test_filter_by_budget(sample_restaurants):
    budget_cfg = {"low_max": 500.0, "medium_max": 1200.0}
    # Jassi De Paranthe (Cost for two 400.0) -> Low budget
    assert filter_by_budget(sample_restaurants[0], "low", budget_cfg) is True
    assert filter_by_budget(sample_restaurants[0], "medium", budget_cfg) is False
    
    # The Black Pearl (Cost for two 1400.0) -> High budget
    assert filter_by_budget(sample_restaurants[2], "high", budget_cfg) is True
    assert filter_by_budget(sample_restaurants[2], "medium", budget_cfg) is False
    
    # New Restaurant (Cost for two None) -> Should return False if filter set
    assert filter_by_budget(sample_restaurants[4], "low", budget_cfg) is False
    # Should return True if no filter set
    assert filter_by_budget(sample_restaurants[4], None, budget_cfg) is True

def test_apply_filters(sample_restaurants):
    app_cfg = {
        "filter": {"candidate_cap": 2, "null_rating_policy": "exclude"},
        "budget": {"fixed_bands": {"low_max": 500.0, "medium_max": 1200.0}}
    }
    
    # User Preferences: Indiranagar, medium/low budget, rating >= 4.0
    prefs = UserPreferences(
        location="Indiranagar",
        budget_band="low",
        cuisines=[],
        min_rating=4.0,
        top_k=2
    )
    
    candidate_set = apply_filters(sample_restaurants, prefs, app_cfg)
    # Only Corner House Ice Creams (Indiranagar, Cost 250, Rating 4.6) should match
    assert len(candidate_set.restaurants) == 1
    assert candidate_set.restaurants[0].name == "Corner House Ice Creams"
    assert candidate_set.total_after_hard_filters == 1
    assert candidate_set.capped_to is None
    
    # Test capping
    app_cfg["filter"]["candidate_cap"] = 1
    prefs_any = UserPreferences(
        location="Bangalore",
        min_rating=4.0,
        top_k=5
    )
    # Corner House, Jassi, Black Pearl, Toit match (4 matches total)
    candidate_set_capped = apply_filters(sample_restaurants, prefs_any, app_cfg)
    assert len(candidate_set_capped.restaurants) == 1
    assert candidate_set_capped.total_after_hard_filters == 4
    assert candidate_set_capped.capped_to == 1
